try:
	import Gimp
	import Gegl
except:
	pass

def dir_pretty(obj): print(*dir(obj), sep='\n')

def props_pretty(filter):
	props = [p.get_name() for p in filter.list_properties()]
	print(*props, sep='\n')

def copy_layer(layer, name, order=0):
	new_layer = layer.copy()
	new_layer.set_name(name)
	layer.get_image().insert_layer(new_layer, None, order)
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

def get_histogram(drawable, step=4):
	hist = []
	for i in range(0, 256, step):
		low = i
		high = i + (step - 1)
		# stats = drawable.histogram(Gimp.HistogramChannel.VALUE, low, high)
		stats = drawable.histogram(Gimp.HistogramChannel.VALUE, low / 255, high / 255)
		hist.append(stats.percentile)
		Gimp.progress_update(i / 255)
	Gimp.progress_update(1.0)
	return hist

def find_end(h_array, start, threshold=0.99):
	step = 256 // len(h_array)
	total = 0
	for i in range(start // step, len(h_array)):
		total = total + h_array[i]
		if total > threshold: break
	return i * step + (step - 1)

def histogram_minmax_impl(drawable, h_array, epsilon=0.01, step=4):
	start = next(i for i, x in enumerate(h_array) if x > epsilon) * step
	end = find_end(h_array, start)
	return start, end, drawable.get_image().get_precision(), h_array

def histogram_minmax(drawable, epsilon=0.01, step=4):
	h_array = get_histogram(drawable, step)
	return histogram_minmax_impl(drawable, h_array, epsilon, step)

def alpha_to_selection(layer):
	layer.get_image().select_item(Gimp.ChannelOps.REPLACE, layer)

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
spread_layer_count = 3		# how many layers
spread_incr = 12			# how wide they get
rill_offset_v = 0			# how high to start the rills
rill_step_offset_v = 6		# how tall each layer is
outline_growth_factor = 8
outline_shrink_factor = 3
final_base_v = 10
gamma = 1.55
step = 2

# change image encoding to linear
img.convert_precision(Gimp.Precision.U8_LINEAR)

# get range
Gimp.progress_set_text('Finding min and max intensities...')
low_v, high_v, _, _ = histogram_minmax(sand_layer, step=step)
v_range = nearest * (high_v - low_v) // nearest

Gimp.progress_set_text('Processing...')
# shift sand layer down to base_v of 100
shift_levels_gegl(sand_layer, low_v, high_v, base_v, base_v + v_range)

# make dedent layer 95 "indent - 95"
text_layer.invert(False)
indent_v = base_v + v_range // 2 + indent_offset_v
indent_layer = copy_layer(text_layer, f"indent - {indent_v}")
shift_levels_gegl(indent_layer, 255, 255, indent_v, indent_v)

# make white outline layer (8px grow, 8px shrink)
outline_layer = copy_layer(text_layer, "outline")
alpha_to_selection(text_layer)
Gimp.Selection.grow(img, outline_growth_factor)
Gimp.context_set_foreground(Gegl.Color.new("white"))
outline_layer.edit_fill(0)
alpha_to_selection(text_layer)
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
	l = copy_layer(outline_layer, f"spread - {spread_dist} @ {v}")
	shift_levels_gegl(l, 255, 255, v, v)
	spread(l, spread_dist)
	spread_layers.append(l)

outline_layer.set_visible(False)
text_layer.set_visible(False)

# img.convert_precision(Gimp.Precision.U8_NON_LINEAR)

img.merge_visible_layers(Gimp.MergeType.EXPAND_AS_NECESSARY)
sand_layer = img.get_layer_by_name('sand')
Gimp.progress_set_text('Finding new min and max intensities...')
new_low_v, new_high_v, _, h_data = histogram_minmax(sand_layer, step=step)

# signature
Gimp.progress_set_text('Adding signature...')
signature = "afiril"
font_size = 128
text_vertical_offset = 75
sig_indent_v = base_v + v_range // 2 + 2 * indent_offset_v

font = Gimp.Font.get_by_name('Sans-serif Bold Italic')
# hex_v = format(int(indent_v * gamma), 'x')
hex_v = format(indent_v, 'x')
Gimp.context_set_foreground(Gegl.Color.new('white'))
extents = Gimp.text_get_extents_font(signature, font_size, font)
x = (img.get_width() - extents.width) / 2
y = img.get_height() - text_vertical_offset - extents.height
signature_layer = Gimp.text_font(img, None, x, y, signature, -1, True, font_size, font)
# we're in linear space and Color.new() only does non-linear, so shift to the desired color instead.
shift_levels_gegl(signature_layer, 255, 255, indent_v, indent_v)
img.merge_down(signature_layer, 0)

sand_layer = img.get_layer_by_name('sand')
shift_levels_gegl(sand_layer, new_low_v, new_high_v, final_base_v, final_base_v + (new_high_v - new_low_v + 1))
img.convert_precision(Gimp.Precision.U8_NON_LINEAR)

Gimp.progress_set_text('Done.')
Gimp.progress_update(1.0)
Gimp.progress_end()
