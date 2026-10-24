# Texture Workshop

Texture Workshop (formerly DDS Workshop) helps convert Microsoft Train Simulator / Open Rails textures. It converts ACE texture files to PNG files, and converts edited PNG files to DDS files.

Most users should download the Texture Workshop release ZIP, extract the whole folder, and run `TextureWorkshop.exe`. You do not need Python and you do not need to install ImageMagick when the release includes the `ImageMagick` folder.

## Texture Workshop quick start

1. Extract the release ZIP to a normal folder, such as `C:\Tools\TextureWorkshop`.
2. Run `TextureWorkshop.exe`.
3. Choose a source file or folder.
4. Choose a conversion mode:
   - ACE to editable PNG
   - PNG/TGA/BMP to DDS
   - ACE directly to DDS
5. For DDS output, choose the DDS compression mode:
   - Auto: DXT1 for opaque images, DXT5 for images with transparency
   - Force DXT1
   - Force DXT5
6. For DDS output, choose whether to generate DDS mipmaps.
7. Choose whether to use the source folder or a separate output folder.
8. Click `Run Conversion`.

Keep these files and folders together:

   TextureWorkshop.exe
   ace2png.exe
   png2dds.exe
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

Put ace2png.exe and png2dds.exe somewhere easy to find, such as the same folder as your texture files or a tools folder like C:\PROGRAMS.

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

## Notes

- Existing PNG or DDS files are not simply overwritten. The old file is kept as a backup with .bak added to the name.
- png2dds.exe defaults to automatic DXT selection: DXT1 for images without transparency and DXT5 for images with transparency. Use `--compression dxt1` or `--compression dxt5` to force a specific DDS format.
- png2dds.exe defaults to no mipmaps. Use `--mipmaps generate` to create DDS mipmap levels.
- The old png2dds.ps1 file is no longer needed. PNG to DDS conversion is now handled by png2dds.exe / png2dds.py.

## For developers

To run the source scripts directly, install Python 3 and Pillow:

   pip install Pillow

png2dds.py also needs ImageMagick installed.

To build TextureWorkshop.exe and create the release ZIP:

   python toolsuild_texture_workshop_release.py

The release folder and ZIP are created in the dist folder as TextureWorkshop-<version>.

To regenerate the application icon:

   python toolsuild_texture_workshop_assets.py

Pete Willard, Nov. 2025
