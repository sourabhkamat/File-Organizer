# Changelog

## [v1.1]

### Fixed
- Undo memory loss when organizing multiple folders at once
- Improved stability and logic for **Manage Presets**, including search, edit, and preset customization

### Improved
- File Puller stability
- Context menu ordering for better usability and consistency
- **Delete Empty Folders** now safely skips locked or restricted directories and removes complete empty directory trees instead of deleting one folder per call

### Installer
- Preserves `user_presets.json` across uninstall and reinstall
- Start Menu shortcuts are no longer created
- All dependencies are bundled (no runtime installations required)
