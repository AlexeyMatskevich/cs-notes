#!/usr/bin/env bash
# Development environment setup script
# Called automatically by devbox init_hook

# Calculate hash of current LSP paths to detect changes
marksman_info="$(which marksman 2>/dev/null):$(marksman --version 2>/dev/null || echo 'unknown')"
current_hash=$(echo "$marksman_info" | sha256sum | cut -d' ' -f1)
stored_hash=""
if [ -f .zed/.lsp-hash ]; then
  stored_hash=$(cat .zed/.lsp-hash)
fi

# Regenerate .zed/settings.json if paths changed or file doesn't exist
if [ ! -f .zed/settings.json ] || [ "$current_hash" != "$stored_hash" ]; then
  echo "Generating .zed/settings.json..."
  mkdir -p .zed
  cat > .zed/settings.json << EOF
{
  "lsp": {
    "marksman": {
      "binary": {
        "path": "$(which marksman)"
      }
    }
  }
}
EOF
  echo "$current_hash" > .zed/.lsp-hash
fi
