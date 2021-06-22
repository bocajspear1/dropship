import shlex
import argparse
import logging
import sys
import os
import getpass
import json
from colorama import Fore, Back, Style

import dropship
from dropship.lib.netdef import NetworkDefinition
from dropship.lib.helpers import ModuleManager
from dropship.lib.builder import DropshipBuilder

logger = logging.getLogger('dropship')

def parse_section(section):
    def_holder = NetworkDefinition(section)
    ok = def_holder.parse()
    if ok:
        logger.info("Found network definition '{}'".format(def_holder.name))
    else:
        logger.error("Parsing network definition failed")
        sys.exit(3)
    if def_holder.name == "":
        logger.error("No name in network definition")
        sys.exit(3)
    return def_holder

def create_instance(def_map, inst_data):

    lines = inst_data.split("\n")
    for line in lines:
        if line.startswith("INSTOF"):
            netinst_split = shlex.split(line, " ")
            if len(netinst_split) != 2:
                logger.error("Invalid INSTOF line: '{}'".format(line))
                sys.exit(4)
            def_name = netinst_split[1]
            if def_name not in def_map:
                logger.error("Instance references definition '{}' that has not been defined".format(def_name))
                sys.exit(4)
            
            return def_map[def_name].create_instance(inst_data)
        
    else:
        logger.error("Could not find NETINSTANCE on first line")
        sys.exit(4)
   


def main():
    
    parser = argparse.ArgumentParser(description='Use Dropship')
    parser.add_argument('--defi', help='Network definition(s) file')
    parser.add_argument('--inst', help='Network instance(s) file')
    parser.add_argument('--list', help='List modules')
    parser.add_argument('--config', help='Path to configuration file')
    parser.add_argument('--check', action='store_true', help='Runs a check for unmapped VM names')

    args = parser.parse_args()

    config_path = "./config.json"

    if args.config:
        config_path = args.config 

    if not os.path.exists(config_path):
        print(f"Path to config {config_path} not found")
        sys.exit(1)

    if args.check:
        mm = ModuleManager("./out")

        config_data = json.loads(open(config_path, "r").read())

        module_list = mm.list_modules()
        print(f"{'Module':40} {'Image':40}{'Image':10}{'Creds':10}")
        print("-" * 110)
        for module in module_list:
            mod_obj = mm.get_module(module)
            mod_obj_image = mod_obj.__IMAGE__
            out_str = f"{module:40} {mod_obj_image:40}"
            if mod_obj_image not in config_data["vm_map"]:
                out_str += Fore.RED + f"{'NOT FOUND':10}" + Style.RESET_ALL
            else:
                out_str += Fore.GREEN + f"{'FOUND':10}" + Style.RESET_ALL
            if mod_obj_image not in config_data["credentials"]:
                out_str += Fore.RED + f"{'NOT FOUND':10}" + Style.RESET_ALL
            else:
                out_str += Fore.GREEN + f"{'FOUND':10}" + Style.RESET_ALL
            
            print(out_str)
            

    elif (args.defi is not None and args.inst is None) or (args.defi is None and args.inst is not None):
        logger.error('--defi or --inst not set')
        sys.exit(1)
    elif args.defi is not None and args.inst is not None:
        logger.info('Starting a Dropship run...')
        def_map = {}
        inst_map = {}
        
        builder = DropshipBuilder(config_path)

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
                def_map[def_holder.name] = def_holder
                def_section = ""
                def_section += line + "\n"
            else:
                def_section += line + "\n"
        
        if def_section != "":
            def_holder = parse_section(def_section)
            def_map[def_holder.name] = def_holder
        else:
            logger.error("Got an empty definition")


        logger.debug("Loading network instance data from '{}'".format(args.inst))

        inst_section = ""
        inst_file = open(args.inst, "r")
        inst_data = inst_file.read()
        inst_file.close()

        inst_lines = inst_data.split("\n")
        for i in range(len(inst_lines)):
            line = inst_lines[i].strip()
            if i == 0 and not line.startswith("NETINSTANCE"):
                logger.error("NETINSTANCE line not first line")
                sys.exit(2)
            elif line.startswith("NETINSTANCE") and i > 0:
                instance = create_instance(def_map, inst_section)
                if instance is not None:
                    inst_map[instance.name] = instance
                else:
                    logger.error("Parsing network instance failed")
                    sys.exit(4)
                # def_map[def_holder.name] = def_holder
                inst_section = ""
                inst_section += line + "\n"
            else:
                inst_section += line + "\n"
        
        if inst_section != "":
            instance = create_instance(def_map, inst_section)
            if instance is not None:
                inst_map[instance.name] = instance
            else:
                logger.error("Parsing network instance failed")
                sys.exit(4)
        else:
            logger.error("Got an empty instance")

        for instance in inst_map:
            inst_map[instance].describe()
            builder.add_instance(instance, inst_map[instance])
        
        builder.init_provider()

        if not builder.provider.has_cache():
            username = input("Provider username> ")
            password = getpass.getpass("Provider password> ")
            builder.provider.connect(username, password)
        else:
            builder.provider.connect_cache()
        builder.run_build()

    elif args.list is not None:
        mm = ModuleManager("./out")
        

if __name__ == '__main__':
    main()