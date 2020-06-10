import shlex
import argparse
import logging
import sys

import dropship
from dropship.lib.netdef import NetworkDefinition
from dropship.lib.helpers import ModuleManager

logger = logging.getLogger('dropship')

def parse_section(section):
    def_holder = NetworkDefinition(section)
    ok = def_holder.parse()
    if ok:
        logger.info("Found network definition '{}'".format(def_holder.name))
    else:
        logger.error("Parsing network definition failed")
        sys.exit(3)

def main():
    
    parser = argparse.ArgumentParser(description='Use Dropship')
    parser.add_argument('--defi', help='Network definition(s) file')
    parser.add_argument('--inst', help='Network instance(s) file')
    parser.add_argument('--list', help='List modules')

    args = parser.parse_args()

    if (args.defi is not None and args.inst is None) or (args.defi is None and args.inst is not None):
        logger.error('--defi or --inst not set')
        sys.exit(1)
    elif args.defi is not None and args.inst is not None:
        logger.info('Starting a Dropship run...')
        def_map = {}

        logger.debug("Loading network definition from '{}'".format(args.defi))

        def_section = ""
        def_file = open(args.defi, "r")
        def_data = def_file.read()
        def_file.close()

        def_lines = def_data.split("\n")
        for line in def_lines:
            line = line.strip()
            if line == "":
                continue
            if def_section == "" and not line.startswith("NETWORK"):
                print(line)
                logger.error("NETWORK line not first line")
                sys.exit(2)
            elif line.startswith("NETWORK") and def_section != "":
                def_holder = parse_section(def_section)

                def_section = ""
                def_section += line + "\n"
            else:
                def_section += line + "\n"
        
        if def_section != "":
            def_holder = parse_section(def_section)
        else:
            logger.error("Got an empty definition")


        logger.debug("Loading network instance data from '{}'".format(args.inst))
    elif args.list is not None:
        mm = ModuleManager()
        

if __name__ == '__main__':
    main()