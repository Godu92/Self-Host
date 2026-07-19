# General details for lldap

- [General details for lldap](#general-details-for-lldap)
  - [General verification (via cmd)](#general-verification-via-cmd)
  - [Samples](#samples)
    - [Gitea](#gitea)

## General verification (via cmd)

```sh
ldapsearch -x -H ldap://localhost:3890 \
  -D "uid=admin,ou=people,dc=localhost" \
  -w "admin123" \
  -b "ou=people,dc=localhost" \
  "(uid=*)" \
  uid cn mail givenname sn sshpubke
```

## Samples

### Gitea

```yaml
# LDAP Connection Details (WORKING)
Server: lldap
Port: 3890
Base DN: dc=localhost

Bind DN: uid=admin,ou=people,dc=localhost
Bind Password: admin123

User Search Base: ou=people,dc=localhost
User Filter: (&(objectClass=inetOrgPerson)(uid=%s))

Attributes:
- Username: uid
- First Name: givenname
- Last Name: sn
- Email: mail
- SSH Public Key: sshpubkey
```
