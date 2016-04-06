#!/usr/bin/env python3

"""
Searches metadata.xml files in Gentoo Portage tree to find proxy maintainers.
"""

import argparse
import os
import subprocess
import sys

import portage
from portage.output import colorize as colorize

projects_xml = os.path.join(portage.portdb.porttrees[0], 'metadata', 'projects.xml')  # TODO: is this valid?
maintainer_needed_colour = 'red'
address_colour = 'yellow'
package_colour = 'green'
field_colour = 'blue'
name_colour = 'teal'


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--portdir', help='Portage tree root', default=portage.portdb.porttrees[0], metavar='DIR')
    parser.add_argument('-n', '--nocolour', help='Do not colourise output', action='store_true')

    subparsers = parser.add_subparsers(help='commands')

    local_parser = subparsers.add_parser('query', help='Query packages from input file or STDIN')
    local_parser.add_argument('-i', '--input', help='Package list', type=argparse.FileType('r'), default='-')
    local_parser.add_argument('-d', '--desc', help='Include maint description', action='store_true')
    local_parser.add_argument('-o', '--orphans', help='List orphan packages only', action='store_true')
    local_parser.add_argument('-m', '--maintainer', help='Show package maintainer', action='store_true')
    local_parser.add_argument('-a', '--address', help='Only packages associated with address')
    local_parser.set_defaults(mode='local')

    user_parser = subparsers.add_parser('users', help='List users who proxy-maintain packages')
    user_parser.add_argument('-a', '--address', help='Only list packages for ADDRESS')
    user_parser.add_argument('-C', '--category', help='Limit results to CATEGORY')
    user_parser.add_argument('-l', '--list-atoms', help='Print list of maintained atoms', action='store_true')
    user_parser.set_defaults(mode='users')

    orphan_parser = subparsers.add_parser('orphans', help='List all orphaned packages')
    orphan_parser.add_argument('-C', '--category', help='Limit results to CATEGORY')
    orphan_parser.add_argument('-i', '--installed', help='Show installed packages only', action='store_true')
    orphan_parser.set_defaults(mode='orphans')

    xml_parser = subparsers.add_parser('xml', help='List users who proxy-maintain packages in XML-style')
    xml_parser.add_argument('-a', '--address', help='Only list packages for ADDRESS')
    xml_parser.add_argument('-C', '--category', help='Limit results to CATEGORY')
    xml_parser.add_argument('-c', '--commits', help='Include last known commit', action='store_true')
    xml_parser.set_defaults(mode='xml')
    
    args = parser.parse_args()

    # print help if no mode is given
    if 'mode' not in args:
        parser.print_help()
        return -1

    # overrides the colorize function with effectively a noop
    if args.nocolour or not sys.stdout.isatty():
        global colorize
        colorize = nocolor

    try:
        if args.category:
            if not portage.portdb.categories.__contains__(args.category):
                print('Error: invalid category specified: %r' % args.category, file=sys.stderr)
                return -3
    except AttributeError:
        args.category = None

    if args.mode == 'local':
        return list_local_packages(args)
    elif args.mode == 'users':
        return list_user_maintainers(args)
    elif args.mode == 'orphans':
        return list_orphan_packages(args)
    elif args.mode == 'xml':
        return print_xml(args)
    else:
        parser.print_help()
        return -1


def list_local_packages(args: argparse.Namespace) -> int:
    """
    List proxy-maint packages installed on system as identified by input.

    :param args: argparse namespace
    """
    assert isinstance(args, argparse.Namespace)

    # don't hang if no input file or pipe
    if args.input.isatty():
        print('ERROR: input file or pipe required for local package lists', file=sys.stderr)
        return 2

    atoms = [line.strip() for line in args.input.readlines()]
    package_list = []
    available_atoms = portage.portdb.cp_all(trees=[args.portdir])

    for atom in atoms:
        # assure we're working with only CP not CPV
        atom = portage.dep.dep_getkey(atom)

        # check if the atom is in the PORTDIR we're using
        if atom not in available_atoms:
            continue

        metadata = os.path.join(args.portdir, atom, 'metadata.xml')
        if not os.path.exists(metadata):
            print('Error: no metadata.xml found for atom: %r' % atom, file=sys.stderr)
            continue

        if args.address:
            xml = portage.xml.metadata.MetaDataXML(metadata, projects_xml)
            matches_address = False
            for maintainer in xml.maintainers():
                if maintainer.email == args.address:
                    matches_address = True
            if not matches_address:
                # package not associated with specified address
                continue
            del xml
            del matches_address

        if args.orphans:
            if atom not in package_list:
                if is_orphan(metadata):
                    package_list.append(atom)
        else:
            if atom not in package_list:
                if is_orphan(metadata) or is_proxy_maintained(metadata):
                    package_list.append(atom)

    package_list.sort()

    if args.orphans:
        print('The following packages are orphaned:')
    elif args.address:
        print('The following packages are associated with the address %r' % args.address)
    else:
        print('The following packages are either orphaned or proxy-maintained:')

    for atom in package_list:
        if args.maintainer:
            metadata = os.path.join(args.portdir, atom, 'metadata.xml')
            if not os.path.exists(metadata):
                print('Error: no metadata.xml found for atom: %r' % atom, file=sys.stderr)
                continue

            xml = portage.xml.metadata.MetaDataXML(metadata, projects_xml)
            print()
            print(_p_pkg(atom))
            if len(xml.maintainers()) == 0:
                print('    %s' % _p_mn('No Maintainer!'))
            else:
                for maint in xml.maintainers():
                    if maint.email == 'maintainer-needed@gentoo.org':
                        print('   %s:' % _p_fld('Maintainer'), _p_mn(maint.email))
                    else:
                        output = '   %s:' % _p_fld('Maintainer')
                        if maint.name is not None:
                            output += ' %s' % _p_name(maint.name)
                        if maint.email is not None:
                            output += ' (%s)' % _p_addr(maint.email)
                        print(output)
                        if args.desc:
                            if maint.description is not None:
                                print('               %s' % maint.description)
                if len(xml.herds()) != 0:
                    for herd in xml.herds():
                        print('         %s: %s' % (_p_fld('Herd'), herd))
        else:
            print(_p_pkg(atom))

    return 0


def print_xml(args: argparse.Namespace) -> int:
    """
    Prints proxy maintainers in a nice XML format.

    :param args: argparse namespace
    """
    assert isinstance(args, argparse.Namespace)

    git_dir = os.path.join(args.portdir, '.git')
    if not os.path.isdir(git_dir):
        print('This functionality only works if --portdir is a git repository.', file=sys.stderr)
        return 1

    maintainers = get_maintainers(args)
    maintainer_list = list(maintainers.keys())
    maintainer_list.sort()

    print('<maintainers>')

    for maintainer in maintainer_list:
        print('  <maintainer>')
        email = maintainer
        name = maintainers[maintainer][0]
        print('    <email>%s</email>' % email)
        if name is not None:
            print('    <name>%s</name>' % name)
        print('    <packages>')
        for atom in maintainers[maintainer][1]:
            if args.commits:
                commit = get_last_commit(atom, args.portdir)
                print('      <package name="%s">' % atom)
                print('        <lastCommitDate>%s</lastCommitDate>' % commit[0])
                print('        <lastCommitAuthor>%s</lastCommitAuthor>' % commit[1])
                print('        <lastCommitTitle>%s</lastCommitTitle>' % commit[2])
                print('        <lastCommitId>%s</lastCommitId>' % commit[3])
                print('      </package>')
            else:
                print('      <package name="%s" />' % atom)
        print('    </packages>')
        print('  </maintainer>')
    print('</maintainers>')
    return 0


def get_last_commit(atom: str, repo: str) -> tuple:
    """
    Looks at git log to find last commit for atom.

    :param atom: the package atom (CP) to look up.
    :param repo: path to repository
    :returns: tuple of (commit-date, commit-author, commit-subj, commit-id)
    """
    assert isinstance(atom, str)
    assert isinstance(repo, str)

    curdir = os.curdir
    os.chdir(repo)

    log = subprocess.check_output(['git', 'log', '-n1', '--format=fuller', atom]).decode()
    log = log.splitlines()

    commit_id = log[0][7:]
    author = log[1][12:]
    auth_date = log[2][12:]
    title = log[6].strip()

    # replace '<' and '>' in author
    author = author.replace('<', '[').replace('>', ']')

    os.chdir(curdir)

    return tuple([auth_date, author, title, commit_id])


def list_user_maintainers(args: argparse.Namespace) -> int:
    """
    Lists all packages that have a non-developer maintainer assigned.

    :param args: argparse namespace
    """
    assert isinstance(args, argparse.Namespace)

    maintainers = get_maintainers(args)

    if args.address:
        # print only info for given address
        try:
            print('%s (%s)' % (_p_addr(args.address), _p_name(maintainers[args.address][0])))
            for atom in maintainers[args.address][1]:
                print('   ', _p_pkg(atom))
        except KeyError:
            print('Error: maintainer address %r not found' % args.address, file=sys.stderr)

    else:
        maintainer_list = list(maintainers.keys())
        maintainer_list.sort()

        for maintainer in maintainer_list:
            email = maintainer
            name = maintainers[maintainer][0]
            if args.list_atoms:
                print()
            if name is not None:
                print('%s <%s>' % (_p_name(name), _p_addr(email)))
            else:
                print(_p_addr(email))
            if args.list_atoms:
                for atom in maintainers[maintainer][1]:
                    print('   ', _p_pkg(atom))

    return 0


def list_orphan_packages(args: argparse.Namespace) -> int:
    """
    Lists all found orphan packages.

    :param args: argparse namespace
    """
    assert isinstance(args, argparse.Namespace)
    for atom in portage.portdb.cp_all(trees=[args.portdir]):
        if args.category and not is_in_category(atom, args.category):
            continue

        metadata_path = os.path.join(args.portdir, atom, 'metadata.xml')
        if not os.path.exists(metadata_path):
            print('Error: no metadata.xml found for atom: %r' % atom, file=sys.stderr)
            continue

        if is_orphan(metadata_path):
            if args.installed:
                if is_installed(atom, args.portdir):
                    print(_p_pkg(atom))
            else:
                print(_p_pkg(atom))

    return 0


def get_maintainers(args: argparse.Namespace) -> dict:
    """
    Iterates through packages and returns a dict of maintainers with their packages.

    :param args: argparse.Namespace
    :rtype: dict
    """
    maintainers = {}
    for atom in portage.portdb.cp_all(trees=[args.portdir]):
        if args.category and not is_in_category(atom, args.category):
            continue

        metadata = os.path.join(args.portdir, atom, 'metadata.xml')
        if not os.path.exists(metadata):
            print('Error: no metadata.xml found for atom: %r' % atom, file=sys.stderr)
            continue

        if args.address:
            # allow searching for any address
            xml = portage.xml.metadata.MetaDataXML(metadata, projects_xml)
            for maintainer in xml.maintainers():
                if maintainer.email == args.address:
                    try:
                        maintainers[args.address]
                    except KeyError:
                        maintainers[args.address] = [maintainer.name, []]
                    maintainers[args.address][1].append(atom)
        elif is_proxy_maintained(metadata):
            xml = portage.xml.metadata.MetaDataXML(metadata, projects_xml)
            for maintainer in xml.maintainers():
                email = maintainer.email
                if 'gentoo.org' not in email:
                    try:
                        maintainers[email]
                    except KeyError:
                        maintainers[email] = [maintainer.name, []]
                    maintainers[email][1].append(atom)

    return maintainers


def is_orphan(metadata: str) -> bool:
    """
    Checks package metadata and determines if package is orphaned.

    :param metadata: Path to package metadata.xml
    :return: True if package is orphan, else False
    """
    assert isinstance(metadata, str)
    xml = portage.xml.metadata.MetaDataXML(metadata, projects_xml)
    herds = xml.herds()
    maintainers = xml.maintainers()

    orphaned = False

    if len(herds) == 0 or (len(herds) == 1 and herds[0][0] == 'proxy-maintainers'):
        if len(maintainers) == 0:
            orphaned = True
        elif len(maintainers) == 1 and maintainers[0].email == 'maintainer-needed@gentoo.org':
            orphaned = True

    return orphaned


def is_installed(atom: str, portdir: str=portage.portdb.porttrees[0]) -> bool:
    """
    Determins if package is installed by checking if directory exists in VDB.

    :param atom: CP or CPV atom to check
    :param portdir: path to portage tree root, defaults to primary tree
    :return: True if package installed, otherwise False
    """
    assert isinstance(atom, str)

    # make sure we're only working with a CP and not a CPV
    atom = portage.dep.dep_getkey(atom)

    for cpv in portage.portdb.cp_list(atom, mytree=[portdir]):
        if os.path.exists(os.path.join(portage.const.VDB_PATH, cpv)):
            return True

    return False


def is_proxy_maintained(metadata: str) -> bool:
    """
    Determines if a package is maintained by someone without an @gentoo.org address.

    :param metadata: path to package metadata
    :return: True if package is proxy-maintained, otherwise False
    """
    assert isinstance(metadata, str)
    assert os.path.exists(metadata)

    xml = portage.xml.metadata.MetaDataXML(metadata, projects_xml)

    if len(xml.maintainers()) > 0:
        for maintainer in xml.maintainers():
            if 'gentoo.org' not in maintainer.email:
                return True

    return False


def is_in_category(atom: str, category: str) -> bool:
    """
    Determines if the given atom is within the specified category.

    :param atom: package atom to check
    :param category: category to compare
    :return: True if atom is in category, otherwise False
    """
    p_cat, p_name = portage.dep.catsplit(atom)
    return p_cat == category


# noinspection PyUnusedLocal
def nocolor(color: str, string: str) -> str:
    """
    Override function if called with --nocolour

    :param color: String for colour to be used (for compat)
    :param string: Text to (not) colourise
    :return:
    """
    return string


def _p_name(name: str) -> str:
    """
    Prints a name consistently.

    :param name: Name to print
    :return: string of colourised name
    """
    return colorize(name_colour, name)


def _p_addr(addr: str) -> str:
    """
    Prints an email address consistently.

    :param addr: Address to print
    :return: colourised address
    """
    return colorize(address_colour, addr)


def _p_pkg(pkg: str) -> str:
    """
    Prints a package name consistently.

    :param pkg: Package name to print
    :return: colourised package name
    """
    return colorize(package_colour, pkg)


def _p_fld(field: str) -> str:
    """
    Prints a field name consistently.

    :param field: Field label to print
    :return: colourised string
    """
    return colorize(field_colour, field)


def _p_mn(txt: str) -> str:
    """
    Prints maintainer-needed text consistently.

    :param txt: Text to print (addr or "Maintainer Needed" etc)
    :return: colourised text
    """
    return colorize(maintainer_needed_colour, txt)


if __name__ == '__main__':
    exit(main())
