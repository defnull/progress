# coding: utf8

import time
import sys
import math
from functools import partial
import itertools
import struct

try:
    IS_TTY = sys.stdout.isatty()
except AttributeError:
    IS_TTY = False


def _csize_unix():
    import termios, fcntl

    if not IS_TTY:
        return None

    s = struct.pack("HHHH", 0, 0, 0, 0)
    fd_stdout = sys.stdout.fileno()
    size = fcntl.ioctl(fd_stdout, termios.TIOCGWINSZ, s)
    height, width = struct.unpack("HHHH", size)[:2]
    return width, height


def _csize_win():
    # http://code.activestate.com/recipes/440694/
    from ctypes import windll, create_string_buffer
    STDIN, STDOUT, STDERR = -10, -11, -12

    h = windll.kernel32.GetStdHandle(STDERR)
    csbi = create_string_buffer(22)
    res = windll.kernel32.GetConsoleScreenBufferInfo(h, csbi)

    if res:
        (bufx, bufy, curx, cury, wattr,
         left, top, right, bottom,
         maxx, maxy) = struct.unpack("hhhhHhhhhhh", csbi.raw)
        return right - left + 1, bottom - top + 1


def _console_width(default=80):

    if sys.platform.startswith('win'):
        width, height = _csize_win()
    else:
        width, height = _csize_unix()

    return width or default
    
    
    


class Progress(object):
    def __init__(self, label='', unit='', scale=1):
        self.label = label
        self.unit = unit
        self.scale = scale
        self.barwidth = 10
        self.interval = 0.4
        self.tps = 0

        now = time.time()
        self.count = 0
        self.expected = None
        self.started = now
        self.last_shown = 0
        self.last_change = now

    def show(self, force=False):
        now = time.time()

        if not force and now - self.last_shown < self.interval:
            return

        self.last_shown = now

        if self.expected:
            todo = self.expected - self.count
            if self.tps == 0:
                eta = self.ftime(-1)
            else:
                elapsed = now - self.last_change
                eta = self.ftime(todo / self.tps - elapsed)

            done, all = self.count // self.scale, self.expected // self.scale

            barlen = done * self.barwidth // all if all else 0
            ws = int(math.log10(all) if all else 0) - int(math.log10(done) if done else 0)

            line = ' [%s%s] %s%i/%i%s ETA %s' % (
                '#' * barlen, ' ' * (self.barwidth - barlen),
                ' ' * ws, done, all, self.unit, eta)
        else:
            chars = u'|/—\\'
            bar = chars[int((now - self.started) / self.interval) % len(chars)]            
            line = u'[%s] %i%s (%.2f %s/s)' % (bar, self.count // self.scale, self.unit, self.tps, self.unit)

        self.print_lr(self.label, line)

    def ftime(self, delta):
        if delta > 60 * 60 * 99 or delta < 0:
            return '**:**:**'
        sec = delta % 60
        mns = (delta // 60) % 60
        hrs = delta // 60 // 60
        return '%02i:%02i:%02i' % (hrs, mns, sec)

    def print_lr(self, label, line):
        cols = _console_width()
        ws = (cols - len(self.label) - len(line))
        if ws < 0:
            label = label[:ws - 4] + '... '
            ws = 0
        sys.stderr.write(label + ' ' * ws + line + '\r')
        sys.stderr.flush()

    def println(self, line):
        line = str(line).rstrip()
        cols = console_width({})
        if len(line) < cols:
            line += ' ' * (cols - len(line))
        sys.stderr.write(line + '\n')
        sys.stderr.flush()

    def wrapiter(self, iterable):
        try:
            self.items = len(iterable)
        except TypeError:
            pass

        for item in iterable:
            self.done += 1
            yield item

    def map(self, func, iterator):
        return map(func, self.wrapiter(iterator))

    def reset(self):
        now = time.time()
        self.items = None
        self.done = 0
        self.started = now

    def set_items(self, n):
        self.expected = n
        self.show(force=True)

    def get_items(self):
        return self.expected or 0

    items = property(get_items, set_items)
    del set_items, get_items

    def set_done(self, n):
        self.count = n
        self.last_change = time.time()
        self.tps = float(self.count) / (self.last_change - self.started)
        if self.expected is not None and self.count > self.expected:
            self.expected = self.count
        self.show()

    def get_done(self):
        return self.count

    done = property(get_done, set_done)
    del set_done, get_done

    def __enter__(self):
        self.reset()
        self.print_lr(self.label, "[...]")
        return self

    def __exit__(self, *a):
        now = time.time()
        delta = now - self.started

        if isinstance(a[1], KeyboardInterrupt):
            return
        if a[1]:
            line = 'ERROR'
        elif self.count:
            line = '(%i%s in %s - %.2f %s/s) DONE' % (
                self.count // self.scale, self.unit, self.ftime(max(1, delta)), self.count / self.scale / delta,
                self.unit or '#'
            )
        else:
            line = 'DONE'

        self.print_lr(self.label, line)
        sys.stderr.write('\n')
        sys.stderr.flush()
        if a[1]:
            sys.stderr.write('  %r\n' % a[1])
            sys.stderr.flush()


