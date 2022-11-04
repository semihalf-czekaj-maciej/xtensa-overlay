#!/usr/bin/env python3

import sys
import json
import pprint
import types
from functools import reduce
from os.path import basename,splitext
import csv

def bits2int(bits):
    ints = (1 << b for b in bits)
    return reduce(lambda a,b: a | b,ints,0)


def js2tuple(js):
    for op in js.opcodes:
        for v in op.variants:
            for a in v.args:
                yield (op.opcode, v.format, v.slot, 
                       hex(bits2int(v.format_bits)),
                       hex(bits2int(v.opcode_bits)),
                       a.arg,
                       a.dir,
                       a.reg,
                       a.num_regs,
                       a.flags,
                       hex(bits2int(a.field_bits))
                       )


def main():
    w = csv.writer(sys.stdout)
    w.writerow("cpu,opcode,format,slot,format_bits,opcode_bits,arg,field_bits".split(","))
    for path in sys.argv[1:]:
        with open(path) as f:
            js = json.load(f,
                    object_hook=lambda d: types.SimpleNamespace(**d))
            name = splitext(basename(path))[0]
            name = name.removeprefix('xtensa_')
            for row in js2tuple(js):
                w.writerow([name]+list(row))

if __name__ == '__main__':
    main()