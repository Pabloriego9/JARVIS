#!/usr/bin/env bash
# Source from the prepared cloud workspace. Does not install or redefine HOME.
export PATH="/workspace/.toolchains/flutter/bin:/workspace/.toolchains/dotnet:/workspace/.toolchains/jdk-21.0.12.1/bin:$PATH"
export JAVA_HOME=/workspace/.toolchains/jdk-21.0.12.1
export ANDROID_HOME=/workspace/.toolchains/android
export ANDROID_USER_HOME=/workspace/.cache/android
export GRADLE_USER_HOME=/workspace/.cache/gradle
export PUB_CACHE=/workspace/.cache/pub
export UV_CACHE_DIR=/workspace/.cache/uv
export npm_config_cache=/workspace/.cache/npm
export DOTNET_CLI_HOME=/workspace/.cache/dotnet
export DOTNET_CLI_TELEMETRY_OPTOUT=1
export NUGET_PACKAGES=/workspace/.cache/nuget
export XDG_CONFIG_HOME=/workspace/.cache/config
export XDG_CACHE_HOME=/workspace/.cache
export ANALYZER_STATE_LOCATION_OVERRIDE=/workspace/.cache/analyzer
export FLUTTER_SUPPRESS_ANALYTICS=true
export DASH__SUPPRESS_ANALYTICS=true
