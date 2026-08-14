#!/usr/bin/env bash
# Remote-access bootstrap for the multi-agent workstation.
#
#   ./bootstrap-remote.sh enable    # step 1: Remote Login + Tailscale (needs sudo)
#   ./bootstrap-remote.sh verify    # step 2: check a key login works, from THIS box
#   ./bootstrap-remote.sh harden    # step 3: keys-only sshd (needs sudo)
#
# Deliberately three steps. `harden` disables password auth, so running it
# before a key login is proven can lock SSH out until you fix it from the
# physical console.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEY="$HOME/.ssh/id_ed25519_macmini"

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
note() { printf '    %s\n' "$*"; }
die()  { printf '\n\033[31merror: %s\033[0m\n' "$*" >&2; exit 1; }

cmd_enable() {
  [[ $EUID -eq 0 ]] || die "run with sudo: sudo $0 enable"

  step "Enabling Remote Login (sshd)"
  systemsetup -setremotelogin on
  note "$(systemsetup -getremotelogin)"

  step "Installing tmux config for the invoking user"
  local u="${SUDO_USER:-$USER}"
  local home; home="$(eval echo "~$u")"
  install -m 644 -o "$u" "$HERE/tmux.conf" "$home/.tmux.conf"
  note "wrote $home/.tmux.conf"

  step "Installing Tailscale as a system daemon"
  # System daemon, not the GUI app: it comes up on boot without anyone logging
  # into the desktop session. A headless box whose VPN needs a GUI login is a
  # box you cannot reach after a reboot.
  if ! /opt/homebrew/bin/brew services list | grep -q '^tailscale.*started'; then
    /opt/homebrew/bin/brew services start tailscale
  fi
  note "tailscaled running"

  step "Next"
  note "1. Authenticate the tailnet:  sudo tailscale up --ssh=false"
  note "   (prints a URL; open it and approve this machine)"
  note "2. Copy the private key to whatever you connect FROM:"
  note "     scp kai@$(scutil --get LocalHostName).local:$KEY ~/.ssh/"
  note "3. Prove it works, then:  sudo $0 harden"
}

cmd_verify() {
  step "Local key-auth check"
  [[ -f "$KEY" ]] || die "missing $KEY — regenerate with ssh-keygen -t ed25519 -f $KEY -N ''"
  grep -qF "$(cut -d' ' -f2 "$KEY.pub")" "$HOME/.ssh/authorized_keys" \
    || die "public key is not in ~/.ssh/authorized_keys"
  note "key present and authorized"

  ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
      -i "$KEY" "$USER@localhost" 'echo ok' >/dev/null 2>&1 \
    && note "key-based ssh to localhost: OK" \
    || die "key-based ssh failed — do NOT run 'harden' yet. Is Remote Login on?"

  step "Tailscale"
  if command -v tailscale >/dev/null 2>&1 && tailscale status >/dev/null 2>&1; then
    note "$(tailscale status --peers=false 2>/dev/null | head -1)"
    note "tailnet name: $(tailscale status --json 2>/dev/null | sed -n 's/.*"DNSName": *"\([^"]*\)".*/\1/p' | head -1)"
  else
    note "tailscale not up yet — run: sudo tailscale up --ssh=false"
  fi
}

cmd_harden() {
  [[ $EUID -eq 0 ]] || die "run with sudo: sudo $0 harden"
  [[ -f "$HERE/99-agent-workstation.conf" ]] || die "missing 99-agent-workstation.conf"

  step "Installing keys-only sshd config"
  install -m 644 "$HERE/99-agent-workstation.conf" /etc/ssh/sshd_config.d/
  sshd -t || die "sshd config test failed — NOT restarting. Fix the config first."
  note "config valid"

  step "Restarting sshd"
  launchctl kickstart -k system/com.openssh.sshd
  note "password auth is now off; keys only"
}

case "${1:-}" in
  enable) cmd_enable ;;
  verify) cmd_verify ;;
  harden) cmd_harden ;;
  *) sed -n '2,10p' "$0"; exit 1 ;;
esac
