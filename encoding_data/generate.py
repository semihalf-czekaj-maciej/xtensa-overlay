#!/usr/bin/env python3

import sys
import json
import pprint
import types
from functools import reduce
from os.path import basename,splitext
import csv

HF4 = set([x[0] for x in csv.reader(open('hifi4list.csv'))])
HF3 = set([x[0] for x in csv.reader(open('hifi3list.csv'))])


def bits2int(bits):
    ints = (1 << b for b in bits)
    return reduce(lambda a,b: a | b,ints,0)


def js2tuple(js):
    for op in js["opcodes"]:
        for v in op["variants"]:
            for a in v["args"]:
                yield (op["opcode"], v["format"], v["slot"], 
                       hex(bits2int(v["format_bits"])),
                       hex(bits2int(v["opcode_bits"])),
                       a["arg"],
                       a["dir"],
                       a["reg"],
                       a["num_regs"],
                       a["flags"],
                       hex(bits2int(a["field_bits"]))
                       )


def main():
    w = csv.writer(open('all.csv','w'))
    w.writerow("cpu,opcode,format,slot,format_bits,opcode_bits,arg,dir,reg,num_regs,flags,field_bits".split(","))
    all_js = []
    hifi3 = {}
    hifi4 = {}
    for path in sys.argv[1:]:
        with open(path) as f:
            js = json.load(f)
                #object_hook=lambda d: types.SimpleNamespace(**d))
            name = splitext(basename(path))[0]
            name = name.removeprefix('xtensa_')
            for row in js2tuple(js):
                w.writerow([name]+list(row))
            #all_js.append(js_extend(js))
            hifi3.update(
                [(op["opcode"],op) for op in js["opcodes"] 
                    if op["opcode"] in HF3])
            hifi4.update(
                [(op["opcode"],op) for op in js["opcodes"] 
                    if op["opcode"] in HF4])
    json.dump(
        list(hifi4.values()),open('hifi4.json','w'),
        indent=2)
    json.dump(
        list(hifi3.values()),open('hifi3.json','w'),
        indent=1)

    f_hf3 = open('XtensaHIFI3InstrInfo.td','w')
    for op in hifi3.values():
        cls = generate_instruction(op,'HIFI3')
        print(cls, file=f_hf3)

    f_hf4 = open('XtensaHIFI4InstrInfo.td','w')
    for op in hifi4.values():
        cls = generate_instruction(op,'HIFI4')
        print(cls, file=f_hf4)

    
def js_extend(js):
    for op in js.opcodes:
        feature = ''
        if op.opcode in HF3:
            feature = 'HIFI3'
        if op.opcode in HF4:
            feature = 'HIFI4'
        op.feature = feature


class_template = """
class {class_name}<list<dag> pattern, InstrItinClass itin = NoItinerary>
    : {inst_class}<(outs {out_list}), (ins {in_list}), "{mnemonic}", pattern>,
    Requires<[{feature}]>
{inst_body}
"""

def set_bits(var, bits):
    return "\n".join("let %s{%d} = 1;" % (var,b) for b in bits)

def field_bits(var, fld, bits):
    return "\n".join(("let %s{%d} = %s{%d};" % (var,b,fld,i) 
            for i,b in enumerate(bits)))

def variant_encoding(op,variant):
    return "\n".join([
            "//format",
            set_bits('Inst',variant["format_bits"]),
            "//opcode",
            set_bits('Inst',variant["opcode_bits"]),
            ])

def contraints(variant):
    clobber = [arg["arg"] for arg in variant["args"]
               if arg["dir"] == 'm' ]
    if len(clobber) == 0:
        return ''
    l = [f"${a} = $%{a}_out, @earlyclobber ${a}_out" for a in clobber]
    return "Let Contraints = %s;" % ', '.join(l)

def arg_name(arg,suffix):
    return arg["arg"] + (suffix if arg["dir"] == 'm' else  '')


def arg_type(arg):
    if arg["reg"]:
        return arg["reg"]
    else:
        return arg["arg"]

def arg_list(variant,adir):
    if adir == 'out':
        sfx = '_out'
        dir_list = "o m".split()
    elif adir == 'in':
        sfx = ''
        dir_list  = "i m".split()

    l = ["%s:$%s" % (arg_type(arg),arg_name(arg,sfx)) 
            for arg in variant["args"] 
            if arg["dir"] in dir_list]
    return ", ".join(l)    

def operands(variant):
    l = ['$'+arg["arg"] for arg in variant["args"]
         if not 'i' in arg["flags"]]
    return ', '.join(l)

def operand_encoding(args):
    l = [field_bits('Inst',a["arg"],a["field_bits"]) for a in args]
    return "//operands\n" + "\n".join(l)

def inst_mangle(inst:str):
    return inst.upper().replace('.','_')

def llvm_builtin_mangle(inst:str):
    return inst.replace('.','_')

def generate_instruction(op, feature):
    #pick 1st variant
    variant = op["variants"][0]
    
    format = variant["format"]
    length = variant["length"]
    opcode = op["opcode"]
    class_name = inst_mangle(f"{opcode}_{format}")
    inst_class = f'XtensaInst{length}'
    in_list = arg_list(variant,'out')
    out_list = arg_list(variant,'in')
    mnemonic = f"{opcode} {operands(variant)}"
    constr = contraints(variant)
    inst_body = "{\n%s\n}\n" % "\n".join([
        constr,
        variant_encoding(op, variant),
        operand_encoding(variant["args"])
    ])
    cls = class_template.format(
        class_name = class_name,
        inst_class = inst_class,
        in_list = in_list,
        out_list = out_list,
        mnemonic = mnemonic,
        inst_body = inst_body,
        feature = feature
        )
    inst_def = generate_instruction_def(op,variant, class_name,not constr)
    return cls + "\n\n" + inst_def

def instrinsic_pattern(op, variant):
    out_list = [(a["arg"],a["reg"]) for a in variant["args"] if a["dir"] == 'o']
    int_name = "int_xtensa_" + llvm_builtin_mangle(op["opcode"])
    args = arg_list(variant,'in')
    if len(out_list) == 1:
        out_var, out_reg = out_list[0]
        return f"(set {out_reg}:${out_var}, ({int_name} {args})"
    elif len(out_list) == 0:
        return f"({int_name} {args})"
    else:
        return ''

def generate_instruction_def(op, variant, class_name:str, gen_pattern:bool):
    inst_name = inst_mangle(op["opcode"])
    pattern = instrinsic_pattern(op, variant) if gen_pattern else ''
    return f"def {inst_name} : {class_name}<[{pattern}]>;"

if __name__ == '__main__':
    main()