import array
import gi
from gi.repository import Gimp

def dir_pretty(obj): print(*dir(obj), sep='\n')

def props_pretty(filter):
	props = [p.get_name() for p in filter.list_properties()]
	print(*props, sep='\n')

def copy_layer(image, layer, name, order=0):
	new_layer = layer.copy()
	new_layer.set_name(name)
	image.insert_layer(new_layer, None, order)
	return new_layer

def spread(layer, spread):
	f = Gimp.DrawableFilter.new(layer, "gegl:noise-spread", "")
	c = f.get_config()
	c.set_property("amount-x", spread)
	c.set_property("amount-y", spread)
	f.update()
	layer.merge_filter(f)
	layer.resize_to_image_size()
	return layer

def apply_bump_map(base_layer, map_layer, invert = True):
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
	return base_layer

def chisel(image, layer):
	procedure = Gimp.get_pdb().lookup_procedure('script-fu-chisel-300')
	config = procedure.create_config()
	config.set_property('run-mode', Gimp.RunMode.NONINTERACTIVE)
	config.set_property('otherImage', image)
	config.set_property('drawable', layer)
	config.set_property('option', 0)			# bump curve (Linear | Spherical | Sinusoidal)
	config.set_property('adjustment', 20)		# bevel width
	config.set_property('adjustment-2', 10)		# bevel softness
	config.set_property('adjustment-3', 1.0)	# bevel roundess
	config.set_property('adjustment-4', 0)		# bevel power
	config.set_property('adjustment-5', 135)	# azimuth
	config.set_property('adjustment-6', 20.0)	# elevation
	config.set_property('adjustment-7', 20)		# depth
	config.set_property('option-2', 0) 			# mode (Chisel-off Edges | Carve-in)
	config.set_property('option-3', 0)			# Location (Inside | Outside)
	config.set_property('adjustment-8', 0)		# post-effect blur
	config.set_property('toggle', False)		# keep bump map
	procedure.run(config)
	return image.get_layer_by_name('text bevel')

def minmax(drawable, start_low=0, start_high=255):
	for lo in range(start_low, start_high):
		_, _, _, _, pixels, count, _ = drawable.histogram(Gimp.HistogramChannel.VALUE, 0.0, lo / 255.0)
		if count > (pixels * 0.001):
			break
			
	for hi in range(start_high, -1, -1):
		_, _, _, _, pixels, count, _ = drawable.histogram(Gimp.HistogramChannel.VALUE, hi / 255.0, 1.0)
		if count > (pixels * 0.001):
			break
	
	print(f"low/high: {lo}/{hi}")
	return lo, hi

def set_text_background_color(image, sand, text, low_value, ratio=0.95):
	image.select_item(Gimp.ChannelOps.REPLACE, text)
	sand.edit_clear()
	norm_lo = low_value / 255.0
	color = Gegl.Color.new("black")
	color.set_rgba(norm_lo * ratio, norm_lo * ratio, norm_lo * ratio, 1.0)
	Gimp.context_set_foreground(color)
	sand.edit_fill(0)
	Gimp.Selection.none(image)

img = Gimp.get_images()[0]
sand_layer = img.get_layer_by_name('sand')
text_layer = img.get_layer_by_name('text')

low_value, high_value = minmax(sand_layer)

set_text_background_color(img, sand_layer, text_layer, low_value)

text_layer.invert(False)

spread_layers = [spread(copy_layer(img, text_layer, f"text - {dist}"), dist) for dist in [10, 20, 20, 30, 40, 50]]

img.select_item(Gimp.ChannelOps.REPLACE, text_layer)
for l in spread_layers:
	l.edit_clear()

Gimp.Selection.none(img)

for l in spread_layers:
	apply_bump_map(sand_layer, l)

Gimp.displays_flush()

text_layer.set_visible(False)
img.merge_visible_layers(0)

sand_layer = img.get_layer_by_name('sand')

l, h = minmax(sand_layer)

l = l / 255.0
h = h / 255.0
width = h - l
offset = l * 0.1

Gimp.Drawable.levels(
	sand_layer,
	Gimp.HistogramChannel.VALUE,
	l * 0.9,		# bracket low end of visible
	h,				# bracket high end of visible
	False,			# don't clamp
	1.0,			# gamma
	offset,			# start of output range
	width + offset,	# top of output range
	False)			# clamp output


levels = [42/255.0 if i > 128 else i/128.0 * 42/255.0 for i in range(0,256)]
sand_layer.curves_explicit(Gimp.HistogramChannel.VALUE, levels)

print("Done.")
