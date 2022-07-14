# coding: utf-8
"""Util functions to select the proper python version"""
from __future__ import print_function
import bisect
import re
import subprocess
import os
import fnmatch
import traceback
import sys
import time
import csv
from contextlib import contextmanager

import config
from config import Path

def ignore_surrogates(original):
    new = original.encode('utf8','ignore').decode('utf8','ignore')
    return new, new != original

class SafeSession(object):

    def __init__(self, session, interrupted=536870912):
        self.session = session
        self.future = []
        self.interrupted = interrupted


    def add(self, element):
        self.session.add(element)

    def dependent_add(self, parent, children, on):
        parent.processed |= self.interrupted
        self.session.add(parent)
        self.future.append([
            parent, children, on
        ])

    def commit(self):
        try:
            self.session.commit()
            if self.future:
                for parent, children, on in self.future:
                    if parent.processed & self.interrupted:
                        parent.processed -= self.interrupted
                    self.session.add(parent)
                    for child in children:
                        setattr(child, on, parent.id)
                        self.session.add(child)
                self.session.commit()
            return True, ""
        except Exception as err:
            if config.VERBOSE > 4:
                import traceback
                traceback.print_exc()
            return False, err
        finally:
            self.future = []

    def __getattr__(self, attr):
        return getattr(self.session, attr)


def to_unicode(text):
    if sys.version_info < (3, 0):
        if isinstance(text, unicode):
            return text
        return str(text).decode("utf-8")
    if isinstance(text, str):
        return text
    return bytes(text).decode("utf-8")


def ext_split(values, ext):
    split = values.split(ext + ";")
    result = []
    for i, name in enumerate(split):
        if i != len(split) - 1:
            result.append(name + ext)
        else:
            result.append(name)
    return result



def vprint(verbose, *args):
    if config.VERBOSE > verbose:
        if verbose > 0:
            print(">" * verbose, *args)
        else:
            print(*args)


@contextmanager
def savepid():
    try:
        pid = os.getpid()
        with open(".pid", "a") as fil:
            fil.write("{}\n".format(pid))
        yield pid
    finally:
        with open(".pid", "r") as fil:
            pids = fil.readlines()

        with open(".pid", "w") as fil:
            fil.write("\n".join(
                p.strip()
                for p in pids
                if p.strip()
                if int(p) != pid
            ) + "\n")


def base_dir_exists(out=None, err=None):
    exists = True
    if config.MOUNT_BASE:
        try:
            exists = config.BASE_DIR.exists()
        except OSError as e:
            if e.errno == 107 and config.UMOUNT_BASE:
                subprocess.call(
                    config.UMOUNT_BASE, shell=True, stdout=out, stderr=err
                )
            exists = config.BASE_DIR.exists()
    return exists


@contextmanager
def mount_umount(out=None, err=None):
    try:
        if not base_dir_exists(out, err) and config.MOUNT_BASE:
            subprocess.call(
                config.MOUNT_BASE, shell=True, stdout=out, stderr=err
            )
        yield
    finally:
        if config.BASE_DIR.exists() and config.UMOUNT_BASE:
            subprocess.call(
                config.UMOUNT_BASE, shell=True, stdout=out, stderr=err
            )


@contextmanager
def mount_basedir(out=None, err=None):
    if not base_dir_exists(out, err) and config.MOUNT_BASE:
        subprocess.call(
            config.MOUNT_BASE, shell=True, stdout=out, stderr=err
        )
    yield



def version_string_to_list(version):
    """Split version"""
    return [
        int(x) for x in re.findall(r"(\d+)\.?(\d*)\.?(\d*)", version)[0]
        if x
    ]

def specific_match(versions, position=0):
    """Matches a specific position in a trie dict ordered by its keys
    Recurse on the trie until it finds an end node (i.e. a non dict node)
    Position = 0 indicates it will follow the first element
    Position = -1 indicates it will follow the last element
    """
    if not isinstance(versions, dict):
        return versions
    keys = sorted(list(versions.keys()))
    return specific_match(versions[keys[position]], position)

def best_match(version, versions):
    """Get the closest version in a versions trie that matches the version
    in a list format"""

    if not isinstance(versions, dict):
        return versions
    if not version:
        return specific_match(versions, -1)
    if version[0] in versions:
        return best_match(version[1:], versions[version[0]])
    keys = sorted(list(versions.keys()))
    index = bisect.bisect_right(keys, version[0])
    position = 0
    if index == len(keys):
        index -= 1
        position = -1
    return specific_match(versions[keys[index]], position)

def get_pyexec(version, versions):
    return str(
        config.ANACONDA_PATH / "envs"
        / best_match(version, versions)
        / "bin" / "python"
    )


def invoke(program, *args):
    """Invoke program"""
    return subprocess.check_call([program] + list(map(str, args)))


def find_files(path, pattern):
    """Find files recursively"""
    for root, _, filenames in os.walk(str(path)):
        for filename in fnmatch.filter(filenames, pattern):
            f = Path(root) / filename
            new_name = str(f).encode('utf-8', 'surrogateescape').decode('utf-8', 'replace')
            f.rename(new_name)
            yield Path(new_name)


def find_names(names, pattern, fn=Path):
    """Find path names in pattern"""
    for name in fnmatch.filter(names, pattern):
        yield fn(name)


def join_paths(elements):
    """Join paths by ;"""
    return ";".join(map(str, elements))


def find_files_in_path(full_dir, patterns):
    """Find files in path using patterns"""
    full_dir = str(full_dir)
    return [
        [
            file.relative_to(full_dir)
            for file in find_files(full_dir, "*" + pattern)
            if file.name == pattern
        ] for pattern in patterns
    ]

def find_files_in_zip(tarzip, full_dir, patterns):
    names = tarzip.getnames()
    full_dir = str(full_dir)
    return [
        [
            file.relative_to(full_dir)
            for file in find_names(names, "*" + pattern)
            if file.name == pattern
        ] for pattern in patterns
    ]

def _target(queue, function, *args, **kwargs):
    """Run a function with arguments and return output via a queue.
    This is a helper function for the Process created in _Timeout. It runs
    the function with positional arguments and keyword arguments and then
    returns the function's output by way of a queue. If an exception gets
    raised, it is returned to _Timeout to be raised by the value property.
    """
    try:
        queue.put((True, function(*args, **kwargs)))
    except:
        #traceback.print_exc()
        queue.put((False, sys.exc_info()[1]))

def check_exit(matches):
    path = Path(".exit")
    if path.exists():
        with open(".exit", "r") as f:
            content = set(f.read().strip().split())
            if not content or content == {""}:
                return True
            return matches & content
    return False

from timeout_decorator import timeout, TimeoutError, timeout_decorator
timeout_decorator._target = _target

class StatusLogger(object):

    def __init__(self, script="unknown"):
        self.script = script
        self._count = 0
        self._skipped = 0
        self._total = 0
        self.time = time.time()
        config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.file = config.LOGS_DIR / "status.csv"
        self.freq = config.STATUS_FREQUENCY.get(script, 5)
        self.pid = os.getpid()

    @property
    def count(self):
        return self._count

    @count.setter
    def count(self, value):
        self._count = value
        self._total = self._skipped + self._count

    @property
    def skipped(self):
        return self._skipped

    @skipped.setter
    def skipped(self, value):
        self._skipped = value
        self._total = self._skipped + self._count

    @property
    def total(self):
        return self._total

    def report(self):
        if self.total % self.freq == 0:
            with open(str(self.file), "w") as csvfile:
                writer = csv.writer(csvfile)
                now = time.time()
                writer.writerow([
                    config.MACHINE, self.script,
                    self.total, self.count, self.skipped,
                    self.time, now, now - self.time, self.pid
                ])

def human_readable_duration (duration):
    if duration is None:
        return
    if (duration < 1000):
        return str(round(duration)) + 'ms'

    human_readable_duration = ''

    days = floor(duration / 86400000)
    if days:
        human_readable_duration += str(days) + 'd '

    duration %= 86400000

    hours = floor(duration / 3600000)
    if (days | hours):
        human_readable_duration += str(hours) + 'h '
    duration %= 3600000

    mins = floor(duration / 60000)
    if (days | hours | mins):
        human_readable_duration += str(mins) + 'm'
    duration %= 60000

    secs = duration / 1000
    if (not days):
        if hours | mins > 1:
            decimals = 0
        elif secs > 10:
            decimals = 1
        else:
            decimals = 2
        human_readable_duration += (' ' if human_readable_duration else '') + str(round(secs, decimals)) + 's'

    return human_readable_duration
