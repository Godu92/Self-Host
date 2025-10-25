# General deatils for lldap

## LDAP Connection Details for lldap

Server/Host: <http://lldap> (or ldap.localhost from outside Docker)
Port: 3890
Protocol: LDAP (unencrypted) - or 636 for LDAPS if you set it up
Base DN: dc=localhost

## Bind Credentials (for service accounts)

Bind DN: uid=admin,ou=people,dc=localhost
Bind Password: admin123

## Search Bases

Users: ou=people,dc=localhost
Groups: ou=groups,dc=localhost

## Common Filters

User Filter: (&(objectClass=person)(uid=%s))
Group Filter: (objectClass=groupOfUniqueNames)
Admin Filter: (memberOf=cn=admins,ou=groups,dc=localhost)

## Attributes

Username: uid
Email: mail
First Name: givenName
Last Name: sn
Display Name: cn
SSH Public Key: sshpubkey (needs to be added in lldap UI)
