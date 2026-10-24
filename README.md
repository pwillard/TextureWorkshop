# Texture Workshop

Texture Workshop (formerly DDS Workshop) helps convert Microsoft Train Simulator / Open Rails textures. It converts ACE texture files to PNG files, and converts edited PNG/TGA/BMP files to DDS or ACE files.

Most users should download the Texture Workshop release ZIP, extract the whole folder, and run `TextureWorkshop.exe`. You do not need Python and you do not need to install ImageMagick when the release includes the `ImageMagick` folder.

The full user guide is `Documentation\TextureWorkshop_User_Guide.pdf` in the release folder.

## Texture Workshop quick start

1. Extract the release ZIP to a normal folder, such as `C:\Tools\TextureWorkshop`.
2. Run `TextureWorkshop.exe`.
3. Choose a source file or folder.
4. Choose a conversion mode:
   - ACE to editable PNG
   - ACE directly to DDS
   - PNG/TGA/BMP to DDS
   - PNG/TGA/BMP to ACE
5. For DDS output, choose the DDS compression mode:
   - Auto: DXT1 for opaque images, DXT5 for images with transparency
   - Force DXT1
   - Force DXT5
6. For DDS output, choose whether to generate DDS mipmaps.
7. For ACE output, choose the ACE format:
   - Structured (safest): uncompressed, best compatibility with MSTS and Open Rails
   - DXT1: compressed, for textures without transparency
   - DXT3 or DXT5: compressed, for textures with transparency. Images without an alpha channel are skipped.
   - Auto DXT: DXT1 for opaque images, DXT5 for images with transparency
8. For ACE output, choose whether to generate ACE mipmaps. Mipmaps need square, power-of-two images such as 512x512 or 1024x1024.
9. Choose whether to use the source folder or a separate output folder.
10. Choose what to do with output files that already exist:
   - Ask before overwriting (default): before the run starts, Texture Workshop lists the files that already exist and lets you choose Backup all, Overwrite all, Skip all, or Cancel
   - Skip, Overwrite, or Backup then overwrite: use that choice without asking
11. Click `Run Conversion`.

If two source files would make the same output file, for example `box.png` and `box.tga` both making `box.ace`, Texture Workshop asks before the run which one to convert. You can also skip both. Nothing is converted until you choose.

Keep these files and folders together:

   TextureWorkshop.exe
   ace2png.exe
   png2dds.exe
   png2ace.exe
   ImageMagick\magick.exe

## What you need

### If you are using the EXE files

You need:

1. Windows
2. ImageMagick, either bundled with the release or installed separately

You do not need Python.

### ImageMagick

The preferred release layout includes the official portable ImageMagick build in an `ImageMagick` folder beside the EXE files:

   TextureWorkshop.exe
   ace2png.exe
   png2dds.exe
   png2ace.exe
   ImageMagick\magick.exe

Texture Workshop looks for ImageMagick in this order:

1. The configured ImageMagick path in Settings
2. `ImageMagick\magick.exe` beside Texture Workshop
3. `magick.exe` beside Texture Workshop
4. `magick.exe` on the system PATH

If the release you downloaded already includes the `ImageMagick` folder, you do not need to install ImageMagick separately.

### Install ImageMagick separately

If your release does not include the portable `ImageMagick` folder, install ImageMagick manually:

1. Download the Windows installer:

   https://imagemagick.org/script/download.php#windows

2. Run the installer.

3. When the installer shows extra options, turn on this option:

   Add application directory to your system path

4. Finish the install.

5. Close and reopen your Command Prompt or terminal window.

6. Check that ImageMagick is installed:

   magick -version

If Windows says magick is not recognized, reinstall ImageMagick and make sure the PATH option above is selected.

## Basic use

Put ace2png.exe, png2dds.exe and png2ace.exe somewhere easy to find, such as the same folder as your texture files or a tools folder like C:\PROGRAMS.

### Convert ACE files to PNG

Convert one ACE file:

   ace2png.exe texture.ace

Convert all ACE files in a folder:

   ace2png.exe ace_folder -o png_folder

### Convert PNG files to DDS

Convert one PNG file:

   png2dds.exe texture.png

Convert all PNG files in a folder:

   png2dds.exe png_folder --destination dds_folder

Convert all PNG files in a folder and its subfolders:

   png2dds.exe png_folder --destination dds_folder --recursive

Force DDS compression when needed:

   png2dds.exe texture.png --destination texture.dds --compression dxt1
   png2dds.exe texture.png --destination texture.dds --compression dxt5

Generate DDS mipmaps when needed:

   png2dds.exe texture.png --destination texture.dds --mipmaps generate

### Convert PNG/TGA/BMP files to ACE

Convert one image beside the source file:

   png2ace.exe texture.png

Convert one image to a specific ACE file:

   png2ace.exe texture.png texture.ace

Convert all PNG/TGA files in a folder (not subfolders) into another folder:

   png2ace.exe png_folder ace_folder

Choose a compressed ACE format, or generate mipmaps:

   png2ace.exe texture.png texture.ace --format dxt1
   png2ace.exe texture.png texture.ace --format auto-dxt
   png2ace.exe texture.png texture.ace --mipmaps

png2ace.exe does not need ImageMagick.

## Notes

- In Texture Workshop, existing PNG, DDS or ACE files are never overwritten without your choice. With Backup, the old file is kept with a date stamp and .bak added to the name. When png2ace.exe is used on its own from the command line, it replaces an existing ACE file without a backup.
- png2dds.exe defaults to automatic DXT selection: DXT1 for images without transparency and DXT5 for images with transparency. Use `--compression dxt1` or `--compression dxt5` to force a specific DDS format.
- png2dds.exe defaults to no mipmaps. Use `--mipmaps generate` to create DDS mipmap levels.
- png2ace.exe writes a transparency (alpha) channel only when the image really uses transparency. Tiny amounts of near-opaque alpha are treated as opaque, because some older MSTS ACE readers show stripes when an unneeded alpha channel is present.
- If an ACE conversion is skipped (for example DXT5 chosen for an image with no alpha channel), Texture Workshop leaves any existing ACE file untouched.
- The old png2dds.ps1 file is no longer needed. PNG to DDS conversion is now handled by png2dds.exe / png2dds.py.

## For developers

To run the source scripts directly, install Python 3 and Pillow:

   pip install Pillow

png2dds.py also needs ImageMagick installed.

To build TextureWorkshop.exe and create the release ZIP:

   python tools\build_texture_workshop_release.py

The release folder and ZIP are created in the dist folder as TextureWorkshop-<version>.

The user guide source is `DocSource\TextureWorkshop_User_Guide.adoc`. To rebuild `Documentation\TextureWorkshop_User_Guide.pdf` (needs Ruby with the asciidoctor-pdf gem), run this before building the release:

   python tools\build_user_guide.py

When you change APP_VERSION, also update `:appversion:` in the guide. The build script warns if they differ.

To regenerate the application icon:

   python tools\build_texture_workshop_assets.py

Pete Willard, Nov. 2025
