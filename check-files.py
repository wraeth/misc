#!/usr/bin/env python3

"""
Checks ebuilds in current directory for required files and ensures they exist
within a 'files' subdirectory; as well as listing files in FILESDIR that are
no longer required.
"""

import argparse
import os
import re
import sys

from portage.output import colorize as colorize


error_colour = 'red'
warn_colour = 'yellow'
good_colour = 'green'
cpv_colour = 'blue'
file_colour = 'teal'


def main() -> int:
    """Entry point for CLI usage."""
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', help='Print extra information', action='store_true')
    parser.add_argument('-d', '--debug', help='Print line matches for debug', action='store_true')
    parser.add_argument('-q', '--quiet', help='Print no output (overrides verbose)', action='store_false')
    parser.add_argument('-n', '--nocolour', help='Do not colourise output', action='store_true')
    args = parser.parse_args()

    if args.nocolour:
        global colorize
        colorize = nocolor

    return check_files(args.verbose, args.debug, args.quiet)


def check_files(verbose: bool = False, debug: bool = False, show_output: bool = True) -> int:
    """
    Checks files in $(pwd)/files for required files.

    :param verbose: print extra output
    :return: number of missing required files
    """
    assert isinstance(verbose, bool)
    ebuilds = [f for f in os.listdir('.') if f.endswith('.ebuild')]

    if len(ebuilds) == 0:
        print(_p_error('Error:'), 'not an ebuild directory', file=sys.stderr)
        return 0

    files = {}
    missing_files = 0

    for ebuild in ebuilds:
        P = ebuild[:-7]
        P = re.sub('-r\d+', '', P)
        PN = re.sub('-\d.*', '', P)
        PV = re.search('-\d.*', P).group(0)[1:]

        for line in open(ebuild, 'r').readlines():
            if 'FILESDIR' in line:
                if debug:
                    print('debug:', line.strip())

                line = line.replace('${FILESDIR}', 'files')
                line = line.replace('${P}', P)
                line = line.replace('${PN}', PN)
                line = line.replace('${PV}', PV)
                line = line.replace('"', '')

                try:
                    required_file = re.search('files\S+', line).group(0)
                except AttributeError:
                    print('Error getting path from string: %r' % line.strip(), file=sys.stderr)
                    continue

                try:
                    files[required_file]
                except KeyError:
                    files[required_file] = []
                files[required_file].append(P)

    file_list = list(files.keys())
    file_list.sort()

    if len(file_list) > 0:
        if not os.path.isdir('files'):
            if show_output:
                print(_p_error('Error:'), 'FILESDIR does not exist - %d files missing!' % len(file_list))
        else:
            for f in file_list:
                if not os.path.isfile(f):
                    if show_output:
                        print(_p_file(f), _p_warn('not found'))
                    missing_files += 1
                else:
                    if show_output:
                        print(_p_file(f), _p_good('found'))
                if show_output:
                    if verbose:
                        print('Required by:')
                        [print('   ', _p_pkg(cpv)) for cpv in files[f]]
                        print()

    if os.path.isdir('files'):
        not_required = []
        files_dir = [f for f in os.listdir('files')]
        for f in files_dir:
            path = os.path.join('files', f)
            if path not in files.keys():
                not_required.append(path)

        if show_output:
            if len(not_required) > 0:
                print()
                print('The following files are no longer required:')
                [print('   ', _p_file(f)) for f in not_required]

    return missing_files


# noinspection PyUnusedLocal
def nocolor(color: str, string: str) -> str:
    """
    Override function if called with --nocolour

    :param color: String for colour to be used (for compat)
    :param string: Text to (not) colourise
    :return:
    """
    return string


def _p_good(name: str) -> str:
    """
    Prints good output consistently.

    :param name: Name to print
    :return: string of colourised name
    """
    return colorize(good_colour, name)


def _p_error(addr: str) -> str:
    """
    Prints an error text consistently.

    :param addr: Address to print
    :return: colourised address
    """
    return colorize(error_colour, addr)


def _p_pkg(pkg: str) -> str:
    """
    Prints a package name consistently.

    :param pkg: Package name to print
    :return: colourised package name
    """
    return colorize(cpv_colour, pkg)


def _p_file(field: str) -> str:
    """
    Prints a file name consistently.

    :param field: Field label to print
    :return: colourised string
    """
    return colorize(file_colour, field)


def _p_warn(txt: str) -> str:
    """
    Prints warning text consistently.

    :param txt: Text to print (addr or "Maintainer Needed" etc)
    :return: colourised text
    """
    return colorize(warn_colour, txt)


if __name__ == '__main__':
    exit(main())
