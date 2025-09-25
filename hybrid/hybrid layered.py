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

def minmax(drawable, start_low=0, start_high=255):
	r = start_high - start_low
	for lo in range(start_low, start_high):
		Gimp.progress_update(lo / r * 0.5)
		_, _, _, _, pixels, count, _ = drawable.histogram(Gimp.HistogramChannel.VALUE, 0.0, lo / 255.0)
		if count > (pixels * 0.001):
			break
			
	for hi in range(start_high, -1, -1):
		Gimp.progress_update(lo / r * 0.5)
		_, _, _, _, pixels, count, _ = drawable.histogram(Gimp.HistogramChannel.VALUE, hi / 255.0, 1.0)
		if count > (pixels * 0.001):
			break
	
	Gimp.progress_update(1.0)
	Gimp.progress_set_text(f"low/high: {lo}/{hi}")
	return lo, hi

def alpha_to_selection(image, layer):
	image.select_item(Gimp.ChannelOps.REPLACE, layer)

def shift_levels_gegl(layer, in_low, in_high, out_low, out_high):
	# assumes layer is only white pixels or transparent
	f = Gimp.DrawableFilter.new(layer, "gegl:levels", "")
	c = f.get_config()
	# c.set_property('gamma', 1.0)
	c.set_property('in-low', in_low / 255.0)
	c.set_property('in-high', in_high / 255.0)
	c.set_property('out-low', out_low / 255.0)
	c.set_property('out-high', out_high / 255.0)
	f.update()
	layer.append_filter(f)
	layer.merge_filters()

Gimp.progress_init('Running sand writing...')
Gimp.progress_update(0.0)

img = Gimp.get_images()[0]
sand_layer = img.get_layer_by_name('sand')
text_layer = img.get_layer_by_name('text')

# constants / args
base_v = 100
nearest = 5
indent_offset_v = -5
spread_layer_count = 8
spread_incr = 3
rill_offset_v = 5
rill_step_offset_v = 3
outline_growth_factor = 8
outline_shrink_factor = 3
final_base_v = 75
gamma = 1.55

# change image encoding to linear
img.convert_precision(Gimp.Precision.U8_LINEAR)

# get range
Gimp.progress_set_text('Finding min and max intensities...')
low_v, high_v = minmax(sand_layer)
v_range = nearest * int((high_v - low_v) / nearest)

Gimp.progress_set_text('Processing...')
# shift sand layer down to base_v of 100
shift_levels_gegl(sand_layer, low_v, high_v, base_v, base_v + v_range)

# make dedent layer 95 "indent - 95"
text_layer.invert(False)
indent_v = int(base_v + v_range / 2 + indent_offset_v)
indent_layer = copy_layer(img, text_layer, f"indent - {indent_v}")
shift_levels_gegl(indent_layer, 255, 255, indent_v, indent_v)

# make white outline layer (8px grow, 8px shrink)
outline_layer = copy_layer(img, text_layer, "outline")
alpha_to_selection(img, text_layer)
Gimp.Selection.grow(img, outline_growth_factor)
Gimp.context_set_foreground(Gegl.Color.new("white"))
outline_layer.edit_fill(0)
alpha_to_selection(img, text_layer)
Gimp.Selection.shrink(img, outline_shrink_factor)
outline_layer.edit_clear()
Gimp.Selection.none(img)

# do rill layers
Gimp.progress_set_text('Adding rill layers...')
top_base_v = base_v + v_range
spread_layers = []
for n in range(1, spread_layer_count + 1):
	v = top_base_v + rill_offset_v + (spread_layer_count + 1 - n) * rill_step_offset_v
	spread_dist = spread_incr * n
	l = copy_layer(img, outline_layer, f"spread - {spread_dist} @ {v}")
	shift_levels_gegl(l, 255, 255, v, v)
	spread(l, spread_dist)
	spread_layers.append(l)

outline_layer.set_visible(False)
text_layer.set_visible(False)

img.convert_precision(Gimp.Precision.U8_NON_LINEAR)
img.merge_visible_layers(Gimp.MergeType.EXPAND_AS_NECESSARY)
sand_layer = img.get_layer_by_name('sand')
Gimp.progress_set_text('Finding new min and max intensities...')
new_low_v, new_high_v = minmax(sand_layer, base_v if base_v < indent_v else indent_v, int(1.55 * base_v + spread_layer_count * rill_step_offset_v + rill_offset_v + high_v - low_v))

# signature
Gimp.progress_set_text('Adding signature...')
signature = "afiril"
font_size = 128
text_vertical_offset = 75

font = Gimp.Font.get_by_name('Sans-serif Bold Italic')
hex_v = format(int(indent_v * gamma), 'x')
Gimp.context_set_foreground(Gegl.Color.new(f"#{hex_v}{hex_v}{hex_v}ff"))
extents = Gimp.text_get_extents_font(signature, font_size, font)
x = (img.get_width() - extents.width) / 2
y = img.get_height() - text_vertical_offset - extents.height
signature_layer = Gimp.text_font(img, None, x, y, signature, -1, True, font_size, font)
img.merge_down(signature_layer, 0)

# sand_layer = img.get_layer_by_name('sand')
# shift_levels_gegl(sand_layer, new_low_v, new_high_v, final_base_v, final_base_v + (new_high_v - new_low_v + 1))

Gimp.progress_set_text('Done.')
Gimp.progress_update(1.0)
Gimp.progress_end()
