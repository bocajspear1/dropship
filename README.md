1. Bootstrap - Clone templates and set their addresses and hostnames
2. Deploy - Perform configurations on the systems to make them operational (connect to AD, start services, etc.)
3. Post - Perform after the fact configurations that depend on services (vulnerabilities, data generators, user simulators etc.)


Issues with DNSMasq and UDP checksums: https://github.com/projectcalico/felix/issues/40
```
iptables -A POSTROUTING -t mangle -p udp --dport bootpc -j CHECKSUM --checksum-fill
```