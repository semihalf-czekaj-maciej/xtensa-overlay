#!/usr/bin/env python3

import sys
import json
import pprint
import types
from functools import reduce
from os.path import basename,splitext
import csv

HF4 = set([x[0] for x in csv.reader(open('hf4list.csv'))])
HF3 = set([x[0] for x in csv.reader(open('hf3list.csv'))])


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
    
def js_extend(js):
    for op in js.opcodes:
        feature = ''
        if op.opcode in HF3:
            feature = 'HIFI3'
        if op.opcode in HF4:
            feature = 'HIFI4'
        op.feature = feature

if __name__ == '__main__':
    main()