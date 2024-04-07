# 🏋🏿‍♂️ rezervo

[![rezervo](https://img.shields.io/badge/ghcr.io-mathiazom%2Frezervo-blue?logo=docker)](https://github.com/users/mathiazom/packages/container/package/rezervo)

Automatic booking of group classes

### 🧩 Chains
<div class="image-link-container">
   <a href="https://www.sit.no">
      <img src="assets/badges/chains/sit.svg" alt="sit" height="45">
   </a>
   <a href="https://www.fsc.no">
      <img src="assets/badges/chains/fsc.svg" alt="fsc" height="45">
   </a>
   <a href="https://www.3t.no">
      <img src="assets/badges/chains/3t.svg" alt="3t" height="45">
   </a>
   <a href="https://www.sats.no">
      <img src="assets/badges/chains/sats.svg" alt="sats" height="45">
   </a>
</div>

#### ⚙️ Providers
<div class="image-link-container">
   <a href="https://www.ibooking.no">
      <img src="assets/badges/providers/ibooking.svg" alt="ibooking" height="35">
   </a>
   <a href="https://www.brpsystems.com">
      <img src="assets/badges/providers/brpsystems.svg" alt="brpsystems" height="35">
   </a>
</div>


### 🧑‍💻 Development

#### 🐍 Setup Python environment
1. Ensure Python 3.10+ is installed
2. Install dependencies using Poetry (install from https://python-poetry.org/docs/#installation)
    ```shell
    poetry install
    ```
3. In the [`rezervo`](rezervo) directory, define `.env` and `config.json` based on [`.env.template`](rezervo/.env.template) and [`config.template.json`](rezervo/config.template.json). This includes defining Auth0 tenant details, credentials for Slack notifications and app-wide booking preferences.
   
   <details>
      <summary>📳 Web Push variables</summary>
   
      ##### Web Push variables
      Web push requires a VAPID key pair. This can be generated with the following command using `openssl`:
      ```shell
      openssl ecparam -name prime256v1 -genkey -noout -out vapid_keypair.pem
      ```
      The private key can then be encoded as base64 and added to the `.env` file as `WEB_PUSH_PRIVATE_KEY`:
      ```shell
      openssl ec -in ./vapid_keypair.pem -outform DER|tail -c +8|head -c 32|base64|tr -d '=' |tr '/+' '_-' >> vapid_private.txt
      ```
      Similarly, the public key can be encoded as base64 and included in the client application receiving the notifications:
      ```shell
      openssl ec -in ./vapid_keypair.pem -pubout -outform DER|tail -c 65|base64|tr -d '=' |tr '/+' '_-'|tr -d '\n' >> vapid_public.txt
      ```
   </details>


#### 🐋 Run with Docker
1. Make sure you have defined `.env` and `config.json` as described above
2. With [docker](https://docs.docker.com/get-docker/) and [docker compose](https://docs.docker.com/compose/) installed, run
    ```shell
    docker compose -f docker/docker-compose.dev.yml up -d --build
    ```
3. Within the container, explore available cli commands
    ```shell
    rezervo --help
    ```

#### 🧹 Format and lint
```shell
poe fix
```

#### 🔌 Support new chain
Add your own chain by adding it to `ACTIVE_CHAINS` in [`rezervo/chains/active.py`](rezervo/chains/active.py).

### 🚀 Deployment
A template for a production deployment is given in [`docker-compose.template.yml`](docker/docker-compose.template.yml), which uses the most recent [`rezervo` Docker image](https://github.com/users/mathiazom/packages/container/package/rezervo).
