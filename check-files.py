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

show_output = True
debug = False


def main() -> int:
    """Entry point for CLI usage."""
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', help='Print line matches for debug', action='store_true')
    parser.add_argument('-q', '--quiet', help='Print no output (overrides verbose)', action='store_false')
    parser.add_argument('-n', '--nocolour', help='Do not colourise output', action='store_true')
    parser.add_argument('-p', '--path', help='Path to ebuild directory', default=os.path.abspath(os.curdir))
    args = parser.parse_args()

    if args.nocolour:
        global colorize
        colorize = nocolor

    global show_output
    global debug
    show_output = args.quiet
    debug = args.debug

    try:
        return check_files(args.path)
    except RuntimeError as err:
        print_err(str(err))
        return -1


def check_files(directory: str) -> int:
    """
    Checks files in $(pwd)/files for required files.

    :param directory: path to ebuild directory
    :param debug: output match string for debugging
    :return: number of missing required files
    """
    assert isinstance(directory, str)
    assert isinstance(debug, bool)

    ebuilds = [f for f in os.listdir(directory) if f.endswith('.ebuild')]

    if len(ebuilds) == 0:
        raise RuntimeError('Not a valid ebuild directory: %r' % directory)

    files = {}
    missing_files = 0

    for ebuild in ebuilds:
        P = ebuild[:-7]
        P = re.sub('-r\d+', '', P)
        PN = re.sub('-\d.*', '', P)
        PV = re.search('-\d.*', P).group(0)[1:]

        for line in open(os.path.join(directory, ebuild), 'r').readlines():
            if 'FILESDIR' in line:
                org_line = line.strip()

                # Ignore comment lines
                if re.match('\s*#', line):
                    continue

                line = line.replace('${FILESDIR}', 'files')
                line = line.replace('${P}', P)
                line = line.replace('${PN}', PN)
                line = line.replace('${PV}', PV)
                line = line.replace('"', '')
                line = line.replace('.patch)', '.patch')

                print_dbg('%r -> %r' % (org_line, line.strip()))

                try:
                    required_file = re.search('files\S+', line).group(0)
                except AttributeError:
                    print_err('Unable to get path from string: %r' % line.strip())
                    continue

                try:
                    files[P]
                except KeyError:
                    files[P] = []
                files[P].append(required_file)

    file_list = list(files.keys())
    file_list.sort()

    files_dir_path = os.path.join(directory, 'files')

    if len(file_list) > 0:
        if not os.path.isdir(files_dir_path):
            print_err('FILESDIR does not exist - %d files missing!' % len(file_list))

            # All patch files are missing
            for l in files.values():
                for v in l:
                    missing_files += len(v)

        else:
            for pkg in file_list:
                print_out(_p_pkg(pkg))

                for f in files[pkg]:
                    if not os.path.isfile(os.path.join(directory, f)):
                        print_dbg('PATH NOT FOUND: %r' % os.path.join(directory, 'files', f))
                        print_out(' ', _p_warn('missing:'), _p_file(os.path.basename(f)))
                        missing_files += 1
                    else:
                        print_out(' ', _p_good('  found:'), _p_file(os.path.basename(f)))

    required_files = [v for l in files.values() for v in l]
    print_dbg(required_files)

    if os.path.isdir(files_dir_path):
        not_required = []
        files_dir = [f for f in os.listdir(files_dir_path)]
        for f in files_dir:
            path = os.path.join('files', f)
            if path not in required_files:
                print_dbg('PATH NOT REQUIRED: %r' % path)
                not_required.append(path)

        if len(not_required) > 0:
            print_out('')
            print_out('The following files are no longer required:')
            [print_out('   ', _p_file(os.path.basename(f))) for f in not_required]

    return missing_files


def print_out(*message: list) -> None:
    """
    Wrapper for conditionally printing messages.

    :param message: message to print
    :return: None
    """
    global show_output
    if show_output:
        print(' '.join(message))
    return


def print_err(*message: list) -> None:
    """
    Simple wrapper for printing an error message.

    :param message: error message to print.
    :return: None
    """
    print(_p_error('Error:'), ' '.join(message), file=sys.stderr)
    return


def print_dbg(*message: list) -> None:
    """
    Simple wrapper for printing debug output.

    :param message: error message to print.
    :return: None
    """
    global debug
    if debug:
        print(_p_error('DEBUG: '), ' '.join(message), file=sys.stderr)
    return


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
