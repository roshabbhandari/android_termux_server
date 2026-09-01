# Termux deployment

1. Install a current supported Termux distribution.
2. Keep Android battery optimization disabled for Termux when the device permits it.
3. Run `bash scripts/install.sh` from the repository.
4. Create the owner password during first-run setup. The development password from the planning document is not stored in this repository.
5. Use `scripts/start.sh` and `scripts/healthcheck.sh` to verify the control plane.
6. Configure the boot mechanism available to your Termux build and use `scripts/termux-boot.sh` as the startup entrypoint.
7. For public hosting, configure a named Cloudflare Tunnel after a domain/zone is available.

Android vendor background restrictions vary. A powered-off phone cannot serve requests; recovery only restores service after Android and networking return.
