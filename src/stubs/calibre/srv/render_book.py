"""
WASM stub for calibre.srv.render_book

The content server is not packaged, but calibre.ebooks.oeb.polish.kepubify
(KEPUB output) imports these two helpers from it.
"""


class Profiler:

    def __init__(self):
        import cProfile
        self.profile = cProfile.Profile()

    def __enter__(self):
        self.profile.enable()

    def __exit__(self, *a):
        self.profile.disable()
        self.profile.create_stats()
        import pstats
        stats = pstats.Stats(self.profile)
        stats.sort_stats('cumulative')
        stats.print_stats(.05)


def calculate_number_of_workers(names, in_process_container, max_workers):
    # There are no threads in WASM, always process files sequentially
    return 1
