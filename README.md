# File Organizer

File Organizer is a, customizable file management tool that helps you clean, sort, categorize, and reorganize files efficiently using smart rules. It integrates directly into the Windows File Explorer context menu and provides multiple organizing methods along with a modern GUI for advanced management.

---

## 🚀 Features

### **1. Organize "by Type"**  
Automatically sorts files into folders such as **Images**, **Videos**, **Audio**, **Documents**, **Archives**, etc., based on file extension.

### **2. Organize "by Source" (Domain Extraction)**  
Extracts the **main website name** from URLs embedded in filenames and organizes files into folders like:  
- `Instagram/`  
- `YouTube/`  
- `Pinterest/`  
- `Reddit/`  
- `Pixabay/`  
Regardless of URL format (e.g., `https://www.pixabay.com/photo/xyz`, `img2.reddit.com/file.jpg`, etc.)

Logic used:  
- Ignore prefixes like `www.`, `img2.`, `images.`, `cdn.`, `i.`, etc.  
- Extract only the **first meaningful domain segment**.  
- Remove `.com`, `.in`, `.co`, `.net`, etc.  
- Convert to ProperCase folder names.

### **3. Organize by Category**  
Groups file types into custom categories:  
- **Image Editing Projects** → `.psd`, `.xcf`, `.kra`  
- **Video Projects** → `.prproj`, `.aep`  
- **Code Files** → `.py`, `.js`, `.cpp`, etc.

### **4. Custom File Types (User-defined presets)**  
Built-in GUI:  
- Add new extensions and mapping folders  
- Edit existing rules  
- Search bar  
- Scrollable modern UI  
- Data saved in `user_presets.json`  
- Default rules stored in `default_presets.json`

### **5. File Puller**  
Pulls all files from selected folders (including subfolders) into the parent folder — useful for cleaning huge messy directories.

### **6. Delete Empty Folders**  
Removes empty folders recursively.

### **7. Undo Last Organize**  
Restores moved files to their original locations.  
Also removes **only** the folders that were created during the organize action.


## 🖱️ Context Menu Options

Right‑click inside any folder or on selected folders to access:

```
Organize Files >
    By Category…
    By Type
    By Source
    File Puller >
          Move Out - All Files
          Move Files To "File Bin"   # Only Appears on Selected Folders
          Move Files Out             # Only Appears on Selected Folders
    Delete Empty Folders
    Undo Last Organize
    Multi Rename…
    Manage File Types…
```
