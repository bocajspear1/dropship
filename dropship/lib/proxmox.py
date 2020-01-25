import requests
import time

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
            "newid": nextid
        }

        status, data = self._base.auth_post("{}/qemu/{}/clone".format(self._node_path(), vmid), args)
        print(status, data)

        if status == 200:
            self.tasks.append(data)

    def set_vm_config(self, vmid, config):
        new_config = {}

        for item in config:
            if isinstance(config[item], dict):
                config_string = ""
                if "_item" in config[item]:
                    config_string += config[item]['_item']
                    del config[item]['_item']
                for subitem in config[item]:
                    config_string += "," + subitem + "=" + config[item][subitem]
                new_config[item] = config_string
            else:
                new_config[item] = config[item]

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
    def __init__(self, server_url, ignore_ssl=False):
        if server_url.endswith("/"):
            self._url = server_url[:-1]
        else:
            self._url = server_url
        self._username = ""
        self._ignore_ssl = ignore_ssl
        self._csrf = ""
        self._token = ""


    def auth_post(self, path, data):
        print(path)
        resp = requests.post(
            "{}/api2/json/{}".format(self._url, path), 
            data=data, 
            verify=self._ignore_ssl,
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

    def auth_get(self, path):
        resp = requests.get(
            "{}/api2/json/{}".format(self._url, path), 
            verify=self._ignore_ssl,
            headers={
                "CSRFPreventionToken": self._csrf
            },
            cookies={
                "PVEAuthCookie": self._token
            }
        )
        status = resp.status_code
        if status == 200:
            return status, resp.json()['data']
        else:
            return resp.json()['errors'], None

    def auth_delete(self, path):
        resp = requests.delete(
            "{}/api2/json/{}".format(self._url, path), 
            verify=self._ignore_ssl,
            headers={
                "CSRFPreventionToken": self._csrf
            },
            cookies={
                "PVEAuthCookie": self._token
            }
        )
        status = resp.status_code
        if status == 200:
            return status, resp.json()['data']
        else:
            return resp.json()['errors'], None

    def connect(self, username, password):
        self._username = username
        resp = requests.post("{}/api2/json/access/ticket".format(self._url), data={
            "username": self._username,
            "password": password
        }, verify=self._ignore_ssl)
        

        if resp.status_code == 200:
            self._token = resp.json()['data']['ticket']
            self._csrf = resp.json()['data']['CSRFPreventionToken']
            return True
        else:
            print("Authentication failed!")
            return False

    def Node(self, node_id):
        node = NodeObj(self, node_id)
        status, data = node.get_status()
        if status != 200:
            raise ValueError("Invalid node id")
        else:
            return node

    def get_next_id(self):
        status, data = self.auth_get("/cluster/nextid")
        if status == 200:
            return int(data)
        else:
            return None


class ProxmoxProvider():

    def __init__(self, config):
        # super().__init__(config)
        self._config = config
        self._proxmox = Proxmox(self._config['proxmox']['host'], ignore_ssl=True)

    def connect(self, username, password):
        self._proxmox.connect(username, password)

    def has_template(self, template_name):
        pass

    def clone_vm(self, template, new_name):
        pass
