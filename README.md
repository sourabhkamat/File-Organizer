File Organizer

File Organizer is a customizable Windows file management tool designed to help you clean, sort, categorize, and reorganize files efficiently using smart rules. It integrates directly into the Windows File Explorer context menu and also provides a modern GUI for advanced management and customization.

--------------------------------------------------
FEATURES
--------------------------------------------------

1. Organize by Type
Automatically sorts files into folders such as Images, Videos, Audio, Documents, Archives, Executables, and more, based on file extensions.

2. Organize by Source (Domain Extraction)
Extracts the main website name from URLs embedded in filenames and organizes files into folders like:

Instagram/
YouTube/
Pinterest/
Reddit/
Pixabay/

Works with any URL format, including:
- https://www.pixabay.com/photo/xyz
- img2.reddit.com/file.jpg
- cdn.instagram.com/media/...

Logic used:
- Ignores prefixes like www., img2., images., cdn., i.
- Extracts only the first meaningful domain segment
- Removes domain suffixes like .com, .in, .co, .net
- Converts names into ProperCase folder names

3. Organize by Category
Groups file types into custom categories, such as:
- Image Editing Projects (.psd, .xcf, .kra)
- Video Projects (.prproj, .aep)
- Code Files (.py, .js, .cpp, etc.)

4. Custom File Types (User-defined presets)
Includes a built-in modern GUI to:
- Add new extensions and destination folders
- Edit existing rules
- Search through presets
- Use a clean, scrollable interface

5. File Puller
Pulls all files from selected folders (including subfolders) into a single location. Useful for cleaning deeply nested or messy directories.

6. Delete Empty Folders
Removes empty folders recursively, including entire empty folder trees, while safely skipping locked or restricted folders.

7. Undo Last Organize
- Restores moved files to their original locations
- Removes only the folders created during the last organize action
- Supports Undo Once and Undo All

--------------------------------------------------
CONTEXT MENU OPTIONS
--------------------------------------------------

Right-click inside any folder or on selected folders:

File Organizer >
    By Category...
    By Type
    By Source
    File Puller >
        Move Out - All Files
        Move Files To "File Bin"   (appears only when folders selected)
        Move Files Out             (appears only when folders selected)
    Delete Empty Folders
    Undo Last Organize
    Manage File Types...

--------------------------------------------------
DISCLAIMER
--------------------------------------------------

This is the first public build of File Organizer.

While the app works well overall, there may still be minor bugs, edge cases, or limitations. In particular

If you encounter any unexpected behavior, please report it. Your feedback helps improve the project.

--------------------------------------------------
NOTES
--------------------------------------------------

- Designed for Windows 10 and Windows 11
- Uses the classic File Explorer context menu
- No background services
