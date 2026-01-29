# Docker Registry

A local Docker registry for testing and development. This can be used to host custom images across a network.

- [Docker Registry](#docker-registry)
  - [Quick Start](#quick-start)
  - [Testing Locally](#testing-locally)
    - [1. Tag an existing image for your local registry](#1-tag-an-existing-image-for-your-local-registry)
    - [2. Push the image to your registry](#2-push-the-image-to-your-registry)
    - [3. Remove the local images and pull from your registry](#3-remove-the-local-images-and-pull-from-your-registry)
  - [Common Operations](#common-operations)
    - [List all images in the registry](#list-all-images-in-the-registry)
    - [Delete an image (if deletion is enabled)](#delete-an-image-if-deletion-is-enabled)
    - [Check registry health](#check-registry-health)
  - [Network Usage](#network-usage)
  - [Adding HTTPS/TLS (Production)](#adding-httpstls-production)
    - [Using Corporate Certificates](#using-corporate-certificates)
      - [Option 1: Mount the CA bundle into the registry container](#option-1-mount-the-ca-bundle-into-the-registry-container)
      - [Option 2: Generate self-signed certificates for local testing](#option-2-generate-self-signed-certificates-for-local-testing)
      - [Option 3: Use your corporate CA to sign a certificate](#option-3-use-your-corporate-ca-to-sign-a-certificate)
  - [Adding Basic Authentication (Production)](#adding-basic-authentication-production)
  - [Storage Backend](#storage-backend)
  - [Troubleshooting](#troubleshooting)
    - [Can't push to registry](#cant-push-to-registry)
    - ["connection refused"](#connection-refused)
    - [Images not appearing](#images-not-appearing)
  - [Advanced Configuration](#advanced-configuration)
  - [Useful Links](#useful-links)

## Quick Start

1. Make sure your `.env` file is configured at the project root with:

   ```bash
   HOST=localhost
   ```

2. **IMPORTANT: Configure Docker to allow insecure registries**

   Edit `/etc/docker/daemon.json` (create if it doesn't exist):

   ```json
   {
     "insecure-registries": [
       "dock.localhost",
       "server-or-machine-ip:5000",
       "server-or-machine-ip"
     ]
   }
   ```

   Then restart Docker:

   ```bash
   sudo systemctl restart docker
   ```

3. Start the registry:

   ```bash
   docker compose up -d
   ```

4. Access the registry at: `http://dock.localhost` or `http://server-or-machine-ip:5000`

## Testing Locally

### 1. Tag an existing image for your local registry

```bash
# Pull a test image
docker pull hello-world

# Tag it for your local registry
docker tag hello-world dock.localhost/hello-world:latest
```

### 2. Push the image to your registry

```bash
docker push dock.localhost/hello-world:latest
```

### 3. Remove the local images and pull from your registry

```bash
# Remove local images
docker rmi hello-world dock.localhost/hello-world:latest

# Pull from your registry
docker pull dock.localhost/hello-world:latest

# Run it to verify
docker run dock.localhost/hello-world:latest
```

## Common Operations

### List all images in the registry

```bash
# List repositories
curl http://dock.localhost/v2/_catalog

# List tags for a specific image
curl http://dock.localhost/v2/hello-world/tags/list
```

### Delete an image (if deletion is enabled)

```bash
# Get the digest
curl -I -H "Accept: application/vnd.docker.distribution.manifest.v2+json" \
  http://dock.localhost/v2/hello-world/manifests/latest

# Delete using the digest from the Docker-Content-Digest header
curl -X DELETE http://dock.localhost/v2/hello-world/manifests/<digest>

# Run garbage collection (from inside the container)
docker exec registry bin/registry garbage-collect /etc/docker/registry/config.yml
```

### Check registry health

```bash
curl http://dock.localhost/v2/
```

Expected response: `{}`

## Network Usage

To use this registry across your network:

1. Update your `.env` file:

   ```bash
   HOST=your-server-hostname-or-ip
   ```

2. On client machines, configure Docker to allow insecure registries:

   **Linux (`/etc/docker/daemon.json`):**

   ```json
    {
        "insecure-registries": [
            "dock.localhost",
            "server-or-machine-ip:5000",
            "server-or-machine-ip",
            "host:5000"
        ]
    }
   ```

3. Restart Docker:

   ```bash
   sudo systemctl restart docker
   ```

4. Test from client:

   ```bash
   docker pull dock.your-server-hostname-or-ip:5000/hello-world:latest
   ```

## Adding HTTPS/TLS (Production)

For production use, you should add TLS. Update the compose file with:

```yaml
environment:
  REGISTRY_HTTP_TLS_CERTIFICATE: /certs/domain.crt
  REGISTRY_HTTP_TLS_KEY: /certs/domain.key
volumes:
  - ./certs:/certs
```

### Using Corporate Certificates

If you're in a corporate environment with custom CA certificates:

#### Option 1: Mount the CA bundle into the registry container

```yaml
volumes:
  - ./data:/var/lib/registry
  - /path/to/main/cert/bundle:/etc/ssl/certs/ca-certificates.crt:ro
```

#### Option 2: Generate self-signed certificates for local testing

```bash
mkdir -p certs

# Generate self-signed cert
openssl req -newkey rsa:4096 -nodes -sha256 -keyout certs/domain.key \
  -x509 -days 365 -out certs/domain.crt \
  -subj "/CN=dock.localhost" \
  -addext "subjectAltName=DNS:dock.localhost,IP:server-or-machine-ip"

# Update daemon.json to trust this cert instead of using insecure-registries
sudo mkdir -p /etc/docker/certs.d/dock.localhost
sudo cp certs/domain.crt /etc/docker/certs.d/dock.localhost/ca.crt
sudo systemctl restart docker
```

#### Option 3: Use your corporate CA to sign a certificate

```bash
# Create a certificate signing request
openssl req -newkey rsa:4096 -nodes -keyout certs/domain.key \
  -out certs/domain.csr \
  -subj "/CN=dock.localhost" \
  -addext "subjectAltName=DNS:dock.localhost,IP:server-or-machine-ip"

# Have your corporate CA sign it, then use the signed cert
# Place the signed cert at certs/domain.crt
```

## Adding Basic Authentication (Production)

1. Create a password file:

   ```bash
   mkdir -p auth
   docker run --rm --entrypoint htpasswd httpd:2 -Bbn username password > auth/htpasswd
   ```

2. Update compose file:

   ```yaml
   environment:
     REGISTRY_AUTH: htpasswd
     REGISTRY_AUTH_HTPASSWD_PATH: /auth/htpasswd
     REGISTRY_AUTH_HTPASSWD_REALM: Registry Realm
   volumes:
     - ./auth:/auth
   ```

3. Login from client:

   ```bash
   docker login dock.localhost
   ```

## Storage Backend

By default, images are stored in `./data` directory. For production:

- Consider using object storage (S3, Azure Blob, etc.)
- Set up regular backups
- Monitor disk usage

## Troubleshooting

### Can't push to registry

Check if deletion is enabled and if you have the correct permissions.

### "connection refused"

- Verify the registry is running: `docker ps | grep registry`
- Check Traefik routing: `docker logs traefik`
- Ensure your HOST variable is set correctly

### Images not appearing

```bash
# Check registry logs
docker logs registry

# Verify the image was pushed
curl http://dock.localhost/v2/_catalog
```

## Advanced Configuration

See the [official Docker Registry documentation](https://docs.docker.com/registry/configuration/) for:

- Storage drivers (S3, Azure, GCS, etc.)
- Notifications/webhooks
- Token authentication
- Proxy configuration
- Read-only mode

## Useful Links

- [Docker Registry API](https://docs.docker.com/registry/spec/api/)
- [Registry Configuration Reference](https://docs.docker.com/registry/configuration/)
- [Deploy a registry server](https://docs.docker.com/registry/deploying/)
