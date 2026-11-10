"""Compose avernum_jp.c for Avernum 4 from src_head.c, the shared parts of the Avernum 3 DLL
(logging, exe string replacement, dsound passthrough, data-file redirect) and src_a4.c.

usage: python -I compose_dll.py A3_AVERNUM_JP_C OUT_C
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def section(src, start, end):
    i = src.index(start)
    j = src.index(end, i)
    return src[i:j]


def main(a3_path, out_path):
    a3 = open(a3_path, encoding='utf-8').read()
    head = open(os.path.join(HERE, 'src_head.c'), encoding='utf-8').read()
    a4 = open(os.path.join(HERE, 'src_a4.c'), encoding='utf-8').read()
    log = section(a3, '// ---------------------------------------------------------------- logging',
                  '// ---------------------------------------------------------------- config')
    exe = section(a3, '// ---------------------------------------------------------------- exe string replacement',
                  '// ---------------------------------------------------------------- script token estimate')
    redir = section(a3, '// ---------------------------------------------------------------- translated data files',
                    '// ---------------------------------------------------------------- finding the hook points')
    # Avernum 4: no sprintf hook (positional formats are not used in its exe strings yet)
    exe = exe.replace('#define A_SPRINTF g_va[I_SPRINTF]\n', '')
    i = exe.index('static void install_sprintf_hook(void)')
    j = exe.index('static int is_positional', i)
    exe = exe[:i] + ('static void install_sprintf_hook(void)\n{\n'
                     '    jp_log("positional formats (%%1$s) are not supported in Avernum 4 exe strings\\n");\n}\n\n') + exe[j:]
    # read_all() is defined in the redirect part; the string-table loader uses it too
    out = head + log + exe + redir + a4
    open(out_path, 'w', encoding='utf-8', newline='\n').write(out)
    print('wrote', out_path, out.count('\n'), 'lines')


if __name__ == '__main__':
    main(*sys.argv[1:3])
