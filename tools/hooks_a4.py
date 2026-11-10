"""Hook points of Avernum 4.exe (Steam build) for gen_hooks.py."""

PATTERNS = [
    ('tok_count', 0x457b40, 0x457bb0),   # script token estimate: byte classes
    ('res_start', 0x408e70, 0x408f65),   # "Resolution at Startup" handling
]

VALUES = [
    ('tok_class', 'tok_count', 'at', 0x457b75),
    ('tok_digit', 'tok_count', 'at', 0x457b7d),
    ('tok_other', 'tok_count', 'at', 0x457b84),
    ('tok_letter', 'tok_count', 'at', 0x457ba5),
    ('res_setting', 'res_start', 'abs', 0x4ee3e4),
    ('res_keep', 'res_start', 'at', 0x408eff),
    ('res_keep_back', 'res_start', 'at', 0x408f09),
    ('res_done', 'res_start', 'at', 0x408f56),
]
