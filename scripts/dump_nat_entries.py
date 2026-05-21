#!/usr/bin/env python3

""""
Description: dump_nat_entries.py -- dump conntrack nat entries from kernel into a file
             so as to restore them during warm reboot
"""

import subprocess

def main():
    ctdumpcmd = ['conntrack', '-L', '-j'] 
    file = '/host/warmboot/nat/nat_entries.dump'
    with open(file, 'w') as f:
        p = subprocess.Popen(ctdumpcmd, text=True, stdout=f, stderr=subprocess.PIPE)
    (output, err) = p.communicate()
    rc = p.wait()
    
    if rc != 0:
        print("Dumping conntrack entries failed")
    return

if __name__ == '__main__':
    main()
