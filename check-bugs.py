#!/usr/bin/env python3

"""
Script to check pybugz output and suggest assignment/CC for identified atoms.
"""

import collections
import os
import re
import subprocess

import portage

import portage.dep as dep

Bug = collections.namedtuple('Bug', ['id', 'assignee', 'summary'])
bugz_line = re.compile('(\d+) (\S+) *(.*)')
line_atom = re.compile('(\w+-\w+/\S+)')
package_list = None


def get_bugz_output() -> tuple:
    """
    Runs pybugz and returns the bug list output as a tuple of bug details as named tuples.

    :returns: pybugz bug list, each bug being a named tuple
    :rtype: tuple
    """
    output = subprocess.check_output(['bugz', 'search', '-a', 'bug-wranglers@gentoo.org'])

    bug_list = []

    for line in output.splitlines():
        line = line.decode()
        if not re.search('^\d+', line):
            # this is not a bug line
            continue

        match = re.search('(\d+) (\S+) *(.*)', line)
        if not match:
            raise RuntimeError('Unable to grep the line')

        bug_list.append(Bug(id=match.group(1), assignee=match.group(2), summary=match.group(3)))

    return tuple(bug_list)


def find_atom(summary: str) -> str or None:
    """
    Searches a bug summary line for something that looks like a package atom.

    :param summary: bug summary line to search
    :type summary: str
    :returns: unqualified package atom (CP)
    :rtype: str or None
    """
    assert isinstance(summary, str)
    match = line_atom.search(summary)

    try:
        atom = match.group(1)
    except AttributeError:
        # we still dont' have an atom
        return None

    if atom.endswith(':'):
        atom = atom[:-1]

    if not dep.isvalidatom(atom):
        # try prepending an '='
        if not dep.isvalidatom('='+atom):
            # it's not a valid atom
            return None

    if not dep.isjustname(atom):
        atom = portage.getCPFromCPV(atom)

    # check if we've listed all atoms yet and create the list if not
    global package_list
    if package_list is None:
        package_list = portage.portdb.cp_all()

    if atom in package_list:
        return atom
    else:
        return None


def get_maintainers(atom: str, portdir: str = '/usr/portage') -> tuple:
    """
    Checks the metadata for given package and returns tuple of maintainer emails.

    :param atom: package atom to check
    :type: atom: str
    :param portdir: path to portage tree
    :type portdir: str
    :returns: tuple of ('add@site.com', ...)
    :rtype: tuple
    """
    assert isinstance(atom, str)
    assert isinstance(portdir, str)
    assert os.path.isdir(portdir)
    assert dep.isvalidatom(atom)

    maintainers = []

    metadata_path = os.path.join(portdir, atom, 'metadata.xml')
    if not os.path.exists(metadata_path):
        raise FileNotFoundError('Metadata file not found: %s' % metadata_path)

    xml = portage.xml.metadata.MetaDataXML(metadata_path, '/usr/portage/metadata/projects.xml')

    for maintainer in xml.maintainers():
        maintainers.append(maintainer.email)

    return tuple(maintainers)


def main():
    bugz_output = get_bugz_output()

    string = '%6s  %-30s  %-28s  %s'
    print(string % ('Bug', 'Atom', 'Assignee', 'Maintainers'))
    for bug in bugz_output:
        atom = find_atom(bug.summary)
        if atom is not None:
            maintainers = get_maintainers(atom)
            if len(maintainers) == 0:
                maintainers = tuple(['maintainer-needed@gentoo.org', ''])
            print(string % (bug.id, atom, maintainers[0], ', '.join(maintainers[1:])))
            print('  %s' % bug.summary)
            if len(maintainers) > 1:
                print('  bugz modify -a %s --add-cc %s %s' % (maintainers[0], ' --add-cc '.join(maintainers[1:]), bug.id))
            else:
                print('  bugz modify -a %s %s' % (maintainers[0], bug.id))
            print()


if __name__ == '__main__':
    main()