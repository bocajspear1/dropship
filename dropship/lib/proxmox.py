import requests
import time
import logging
import re

logger = logging.getLogger('dropship')

class NodeObj():
    def __init__(self, base, node_id):
        self._base = base
        self.node_id = node_id
        self.tasks = []

    def _node_path(self):
        return "/nodes/{}".format(self.node_id)

    def clone_vm(self, vmid, new_name, linked=False):
        nextid = self._base.get_next_id()

        full = 0

        if not linked:
            full = 1

        args = {
            "name": new_name,
            "full": full,
            "newid": nextid,
            # For bug: https://bugzilla.proxmox.com/show_bug.cgi?id=2578
            "target": "localhost"

        }

        error, data = self._base.auth_post("{}/qemu/{}/clone".format(self._node_path(), vmid), args)
        print(error, data)

        if error is None:
            self.tasks.append(data)

            return None, nextid
        else:
            return error, 0

    def set_vm_config(self, vmid, config):
        new_config = {}

        for item in config:
            if isinstance(config[item], dict):
                config_string = ""
                if "_item" in config[item]:
                    config_string += config[item]['_item']
                    del config[item]['_item']
                for subitem in config[item]:
                    if config_string != "":
                        config_string += "," + subitem + "=" + config[item][subitem]
                    else:
                        config_string += subitem + "=" + config[item][subitem]
                new_config[item] = config_string
            else:
                new_config[item] = config[item]

        print(new_config)

        status, data = self._base.auth_post("{}/qemu/{}/config".format(self._node_path(), vmid), new_config)
        print(status)
        
        return status, data

    def get_vm_config(self, vmid):
        status, data = self._base.auth_get("{}/qemu/{}/config".format(self._node_path(), vmid))
        return_data = {}
        for item in data:
            value = data[item]
            if isinstance(value, str) and "," in value:
                return_data[item] = {}
                value_split = value.split(",")
                for subitem in value_split:
                    if "=" in subitem:
                    
                        subitem_split = subitem.split("=")
                        subkey = subitem_split[0]
                        subvalue = subitem_split[1]
                        return_data[item][subkey] = subvalue
                    else:
                        return_data[item]["_item"] = subitem
            else:
                return_data[item] = value

            
        return status, return_data

    def start_vm(self, vmid):
        status, data = self._base.auth_post("{}/qemu/{}/status/start".format(self._node_path(), vmid), {})
        return status, data

    def get_status(self):
        return self._base.auth_get("{}/status".format(self._node_path()))


    def wait_tasks(self):
        if len(self.tasks) == 0:
            return
        done = False
        while not done:
            time.sleep(3)
            
            for task in self.tasks:
                error, task_data = self._base.auth_get("{}/tasks/{}/status".format(self._node_path(), task))
                if error is not None:
                    raise ValueError(error)
                elif task_data['status'] == 'stopped':
                    done = True
                else:
                    done = False
            


class Proxmox():
    def __init__(self, server_url, verify_ssl=False):
        if server_url.endswith("/"):
            self._url = server_url[:-1]
        else:
            self._url = server_url
        self._username = ""
        self._verify_ssl = verify_ssl
        if self._verify_ssl:
            logger.warning("Ignoring SSL certificate errors")
        self._csrf = ""
        self._token = ""


    def auth_post(self, path, data):
        
        if not path.startswith("/"):
            path = "/" + path

        resp = requests.post(
            "{}/api2/json{}".format(self._url, path), 
            data=data, 
            verify=self._verify_ssl,
            headers={
                "CSRFPreventionToken": self._csrf
            },
            cookies={
                "PVEAuthCookie": self._token
            }
        )

        status = resp.status_code
        if status == 200:
            return None, resp.json()['data']
        else:
            print(resp.json())
            return resp.json()['errors'], None

    def auth_get(self, path):

        if not path.startswith("/"):
            path = "/" + path

        resp = requests.get(
            "{}/api2/json{}".format(self._url, path), 
            verify=self._verify_ssl,
            headers={
                "CSRFPreventionToken": self._csrf
            },
            cookies={
                "PVEAuthCookie": self._token
            }
        )
        status = resp.status_code
        if status == 200:
            return None, resp.json()['data']
        else:
            return resp.json()['errors'], None

    def auth_delete(self, path):

        if not path.startswith("/"):
            path = "/" + path

        resp = requests.delete(
            "{}/api2/json{}".format(self._url, path), 
            verify=self._verify_ssl,
            headers={
                "CSRFPreventionToken": self._csrf
            },
            cookies={
                "PVEAuthCookie": self._token
            }
        )
        status = resp.status_code
        if status == 200:
            return None, resp.json()['data']
        else:
            return resp.json()['errors'], None

    def connect(self, username, password):
        self._username = username
        resp = requests.post("{}/api2/json/access/ticket".format(self._url), data={
            "username": self._username,
            "password": password
        }, verify=self._verify_ssl)
        

        if resp.status_code == 200:
            self._token = resp.json()['data']['ticket']
            self._csrf = resp.json()['data']['CSRFPreventionToken']
            logger.info("Proxmox authenticated successfully")
            return True
        else:
            logger.error("Proxmox authentication failed")
            return False

    def Node(self, node_id):
        node = NodeObj(self, node_id)
        error, data = node.get_status()
        if error is not None:
            logger.error(error)
            raise ValueError("Invalid node id")
        else:
            return node

    def get_next_id(self):
        error, data = self.auth_get("/cluster/nextid")
        if error is None:
            return int(data)
        else:
            return None


class ProxmoxProvider():

    def __init__(self, config, vm_map):
        # super().__init__(config)
        self._config = config
        self._vm_map = vm_map
        self._proxmox = Proxmox(self._config['host'], verify_ssl=self._config['verify_ssl'])
        self._node = None

    def connect(self, username, password):
        logger.info("Connecting to {}, using node '{}'".format(self._config['host'], self._config['node']))
        self._proxmox.connect(username, password)
        self._node = self._proxmox.Node(self._config['node'])

    def has_template(self, template_name):
        pass

    def clone_vm(self, template, new_name):
        if template not in self._vm_map:
            raise ValueError("Invalid template")

        error, vmid = self._node.clone_vm(self._vm_map[template], new_name, linked=True)
        if error is None:
            logger.info("Creating clone of template {} named {} ({})".format(template, new_name, vmid))
            return vmid 
        else:
            logger.error("Clone failed!")
            logger.error(error)
            return 0

    def start_vm(self, vmid):
        return self._node.start_vm(vmid)

    def set_interface(self, vmid, interface_num, new_switch):
        
        error, vmconfig = self._node.get_vm_config(vmid)
        interface_name = "net{}".format(interface_num)


        if error is None:
            if interface_name not in vmconfig:
                # Just imitate the first interface, kinda lazy
                new_interface_config = vmconfig['net0']
                # Proxmox uses the type as the key type, identify by MAC format
                key = ""
                for item in new_interface_config:
                    if re.match(r"[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}", new_interface_config[item]):
                        key = item
                new_interface_config['model'] = key
                new_interface_config['bridge'] = new_switch
                del new_interface_config[key]
                print(new_interface_config)
                error, data = self._node.set_vm_config(vmid, {interface_name: new_interface_config})
                if error is not None:
                    logger.error(error)
            else:
                update_net = vmconfig[interface_name]
                update_net['bridge'] = new_switch
                error, data = self._node.set_vm_config(vmid, {interface_name: update_net})
                if error is not None:
                    logger.error(error)

    def get_interface(self, vmid, interface_num):
        error, vmconfig = self._node.get_vm_config(vmid)
        interface_name = "net{}".format(interface_num)


        if error is None:
            if interface_name in vmconfig:
                iface_data = vmconfig[interface_name]
                outdata = {
                    "name": interface_name,
                    "switch": iface_data['bridge'],
                    "mac": ""
                }

                for item in iface_data:
                    if re.match(r"[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}", iface_data[item]):
                        outdata['mac'] = iface_data[item]

                return outdata
            else:
                return None

    def wait(self):
        self._node.wait_tasks()
            
    


