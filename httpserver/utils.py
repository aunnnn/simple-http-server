DEBUG_PRINT = True

def __do_nothing(args):
    pass
debugprint = print if DEBUG_PRINT else __do_nothing