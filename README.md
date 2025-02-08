# 🏋🏿‍♂️ rezervo

[![rezervo](https://img.shields.io/badge/ghcr.io-mathiazom%2Frezervo-blue?logo=docker)](https://github.com/users/mathiazom/packages/container/package/rezervo)

Automatic booking of group classes

### 🧩 Chains
<div class="image-link-container">
   <a href="https://sporty.no">
      <img src="assets/badges/chains/sporty.svg" alt="sporty" height="45">
   </a>
   <a href="https://www.3t.no">
      <img src="assets/badges/chains/3t.svg" alt="3t" height="45">
   </a>
   <a href="https://www.sats.no">
      <img src="assets/badges/chains/sats.svg" alt="sats" height="45">
   </a>
   <a href="https://www.sit.no">
      <img src="assets/badges/chains/sit.svg" alt="sit" height="45">
   </a>
</div>

#### ⚙️ Providers
<div class="image-link-container">
   <a href="https://www.brpsystems.com">
      <img src="assets/badges/providers/brpsystems.svg" alt="brpsystems" height="35">
   </a>
   <a href="https://www.ibooking.no">
      <img src="assets/badges/providers/ibooking.svg" alt="ibooking" height="35">
   </a>
</div>


### 🧑‍💻 Development

#### 🐍 Setup Python environment
1. Ensure Python 3.10+ is installed
2. Install dependencies using Poetry (install from https://python-poetry.org/docs/#installation)
    ```shell
    poetry install
    ```
3. In the [`rezervo`](rezervo) directory, define `db.env`, `fusionauth.env` and `config.json` based on [`db.env.template`](rezervo/db.env.template), [`fusionauth.env.template`](rezervo/fusionauth.env.template) and [`config.template.json`](rezervo/config.template.json). This includes defining FusionAuth configuration, credentials for Slack notifications and app-wide booking preferences.
   
   <details>
      <summary>📳 Web Push variables</summary>
   
      ##### Web Push variables
      Web push requires a VAPID key pair. This can be generated with the following command using `openssl`:
      ```shell
      openssl ecparam -name prime256v1 -genkey -noout -out vapid_keypair.pem
      ```
      The private key can then be encoded as base64 and added to the `config.json` file as `notifications.web_push.private_key`:
      ```shell
      openssl ec -in ./vapid_keypair.pem -outform DER|tail -c +8|head -c 32|base64|tr -d '=' |tr '/+' '_-' >> vapid_private.txt
      ```
      Similarly, the public key can be encoded as base64 and included in the client application receiving the notifications:
      ```shell
      openssl ec -in ./vapid_keypair.pem -pubout -outform DER|tail -c 65|base64|tr -d '=' |tr '/+' '_-'|tr -d '\n' >> vapid_public.txt
      ```
   </details>


#### 🐋 Run with Docker
1. Make sure you have defined `db.env`, `fusionauth.env` and `config.json` as described above
2. With [docker](https://docs.docker.com/get-docker/) and [docker compose](https://docs.docker.com/compose/) installed, run
    ```shell
    docker compose -f docker/docker-compose.dev.yml up -d --build
    ```
3. Within the `rezervo` container, initialize FusionAuth
    ```shell
    rezervo fusionauth init
    ```
4. Explore other available cli commands with
    ```shell
    rezervo --help
    ```
   
#### 🦹 FusionAuth Admin Site

The administration tool for FusionAuth is available at [`http://localhost:9011/admin`](http://localhost:9011/admin)

Login credentials for the admin user should be defined in `config.json` under `fusionauth.admin`

#### 🧹 Format and lint
```shell
poe fix
```

#### 🔌 Support new chain
Add your own chain by adding it to `ACTIVE_CHAINS` in [`rezervo/chains/active.py`](rezervo/chains/active.py).

### 🚀 Deployment
A template for a production deployment is given in [`docker-compose.template.yml`](docker/docker-compose.template.yml), which uses the most recent [`rezervo` Docker image](https://github.com/users/mathiazom/packages/container/package/rezervo).
