
# import Gimp
import gi
from gi.repository import Gimp, Gio, Gtk
import os
from os.path import basename, dirname, join

img = Gimp.get_images()[0]
sand_layer = img.get_layer_by_name('sand')
text_layer = img.get_layer_by_name('text')

def dir_pretty(obj): print(*dir(obj), sep='\n')

def props_pretty(filter):
	props = [p.get_name() for p in filter.list_properties()]
	print(*props, sep='\n')

def copy_layer(layer, name):
	new_layer = layer.copy()
	new_layer.set_name(name)
	img.insert_layer(new_layer, None, 0)
	return new_layer

def spread(layer, spread):
	# img.undo_group_start()
	f = Gimp.DrawableFilter.new(layer, "gegl:noise-spread", "")
	c = f.get_config()
	c.set_property("amount-x", spread)
	c.set_property("amount-y", spread)
	f.update()
	layer.merge_filter(f)
	layer.resize_to_image_size()
	# img.undo_group_end()
	return layer

def apply_bump_map(base_layer, map_layer, invert = True):
	# img.undo_group_start()
	bumpmap_filter = Gimp.DrawableFilter.new(base_layer, "gegl:bump-map", "")
	bumpmap_filter.set_aux_input('aux', map_layer)
	bumpmap_filter_config = bumpmap_filter.get_config()
	bumpmap_filter_config.set_property("type", "linear")
	bumpmap_filter_config.set_property("compensate", True)
	bumpmap_filter_config.set_property("invert", invert)
	bumpmap_filter_config.set_property("azimuth", 135.0)
	bumpmap_filter_config.set_property("elevation", 45.0)
	bumpmap_filter_config.set_property("depth", 3)
	bumpmap_filter_config.set_property("offset-x", 0)
	bumpmap_filter_config.set_property("offset-y", 0)
	bumpmap_filter_config.set_property("waterlevel", 1.0)
	bumpmap_filter_config.set_property("ambient", 0.39)
	bumpmap_filter.update()
	base_layer.merge_filter(bumpmap_filter)
	# img.undo_group_end()
	return base_layer

def chisel(image, layer):
	# image.undo_group_start()
	procedure = Gimp.get_pdb().lookup_procedure('script-fu-chisel-300')
	config = procedure.create_config()
	config.set_property('run-mode', Gimp.RunMode.NONINTERACTIVE)
	config.set_property('otherImage', image)
	config.set_property('drawable', layer)
	config.set_property('option', 0)				# bump curve (Linear | Spherical | Sinusoidal)
	config.set_property('adjustment', 20)			   # bevel width
	config.set_property('adjustment-2', 10)			 # bevel softness
	config.set_property('adjustment-3', 1.0)			# bevel roundess
	config.set_property('adjustment-4', 0)			  # bevel power
	config.set_property('adjustment-5', 135)			# azimuth
	config.set_property('adjustment-6', 20.0)		   # elevation
	config.set_property('adjustment-7', 20)			 # depth
	config.set_property('option-2', 0) # mode (Chisel-off Edges | Carve-in)
	config.set_property('option-3', 0)		   # Location (Inside | Outside)
	config.set_property('adjustment-8', 0)			  # post-effect blur
	config.set_property('toggle', False)				# keep bump map
	result = procedure.run(config)
	# success = result.index(0)
	# image.undo_group_end()
	return img.get_layer_by_name('text bevel')

def dir_pretty(obj): print(*dir(obj), sep='\n')

def props_pretty(filter):
	props = [p.get_name() for p in filter.list_properties()]
	print(*props, sep='\n')

text10 = spread(copy_layer(text_layer, "text - 10"), 10)
text20 = spread(copy_layer(text_layer, "text - 20"), 20)
text30 = spread(copy_layer(text_layer, "text - 30"), 30)
Gimp.displays_flush()

img.select_item(Gimp.ChannelOps.REPLACE, text_layer)
text10.edit_clear()
text20.edit_clear()
text30.edit_clear()
Gimp.Selection.none(img)
Gimp.displays_flush()

apply_bump_map(sand_layer, text10)
apply_bump_map(sand_layer, text20)
apply_bump_map(sand_layer, text30)
Gimp.displays_flush()

bevel_layer = chisel(img, text_layer)
bevel_layer.set_opacity(60.0)
img.reorder_item(bevel_layer, None, 3)
text_layer = Gimp.Image.merge_down(img, bevel_layer, 0)
spread(text_layer, 10)
Gimp.displays_flush()

text_layer.set_visible(False)
text10.set_visible(False)
text20.set_visible(False)
text30.set_visible(False)

# apply_bump_map(sand_layer, text_layer, False)

print("Done.")

def save_as():
    dialog = Gtk.FileChooserDialog(
        title="Save File with a Python Plugin",
        action=Gtk.FileChooserAction.SAVE
    )
    dialog.add_buttons(
        Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
        Gtk.STOCK_SAVE, Gtk.ResponseType.OK
    )
	
    dialog.set_current_folder(os.path.dirname(img.get_file().get_path()))
    dialog.set_current_name("my_test.xcf")
	
    filter_xcf = Gtk.FileFilter()
    filter_xcf.set_name("XCF image")
    filter_xcf.add_pattern("*.xcf")
    dialog.add_filter(filter_xcf)
	
    filter_all = Gtk.FileFilter()
    filter_all.set_name("All files")
    filter_all.add_pattern("*")
    dialog.add_filter(filter_all)
	
    response = dialog.run()
	
    if response == Gtk.ResponseType.OK:
        # Get the selected filename from the dialog.
        selected_file_path = dialog.get_filename()
        
        # In a real plugin, you would now use this path to save the image.
        print(f"File selected: {selected_file_path}")
        dialog.destroy()
        
    else:
        # User canceled the dialog.
        print("Save operation canceled.")
        dialog.destroy()
		
    # now save
    if selected_file_path != None:
        gfile = Gio.File.new_for_path(selected_file_path)
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, img, gfile)
