# File Organizer v1.3 - Release Notes

This update drastically improves the reliability of the application, expands what files you can select, and adds deep safety nets to protect your operating system.

## 🐛 Bug Fixes
*   **15-Item Selection Limit Removed:** Fixed an issue where Windows would hide the "File Organizer" context menu if you selected more than 15 files/folders. You can now select an unlimited number of items!
*   **File Puller Menu Fixed:** Resolved an issue where the "File Puller" options were not appearing when a group of folders was manually selected.
*   **Mixed Selection Fix (Files + Folders):** Fixed a major bug where organizing a mixed selection (files and folders together) caused the engine to dig into the selected folders and accidentally extract/rearrange their contents. 
*   **Manage Presets UI Bug:** Fixed an annoying visual glitch in the "Manage Presets" window where typing a new extension and clicking away to type the category would immediately erase what was just typed.

## ✨ New Features & Smarter Logic
*   **Smarter "Background" Execution:** If you right-click the empty background of a folder and click "By Type" or "By Category", the script will now safely *only* target the loose files in that folder. It will no longer dive into sub-folders.
*   **Advanced Whitelisting (`whitelist.Desktop`):** You can now define exceptions for specific folders! For example, you can tell the app to ignore all `.lnk` shortcuts natively sitting on your `Desktop`, while still allowing `.lnk` files to be organized into a "Shortcuts" folder when running the app anywhere else. Whitelist rules are neatly pinned to the top of the GUI.
*   **Reboot-Clearing Undo Memory:** Your Undo History is now physically saved to your hard drive. If you close the app or walk away, you can still safely perform an Undo. However, the app brilliantly detects when your PC restarts and permanently clears the history, freeing up disk space and locking in your changes.

## 🛡️ Enhanced System Safety & Drive Protection
*   Targeting the `C:\Windows`, `C:\Program Files`, `C:\ProgramData`, or the direct root of `C:\Users` is now strictly forbidden, defending your OS from accidental sweeps.
*   Operations directly on the `C:\` System Root are permanently blocked. 
*   Right-clicking the empty background of *any* secondary root drive (like `D:\` or `E:\`) is completely blocked to prevent accidental full-drive scans. 
*   *However*, you are now fully permitted to manually select groups of loose files resting on the root of secondary drives and organize them securely into folders.

