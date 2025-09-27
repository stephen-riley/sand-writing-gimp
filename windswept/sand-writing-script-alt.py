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

def gaussian_blur(layer, radius):
	f = Gimp.DrawableFilter.new(layer, "gegl:gaussian-blur", "")
	c = f.get_config()
	c.set_property("std-dev-x", radius)
	c.set_property("std-dev-y", radius)
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

def find_end(h_array, start, threshold=0.98):
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

def smudge_line(layer, x1, y1, x2, y2, pressure=50):
	Gimp.smudge(layer, pressure, [x1, y1, x2, y2])

def smudges(layer, x_step, pressure=50):
	image = layer.get_image()
	Gimp.context_set_foreground(Gegl.Color.new("white"))
	alpha_to_selection(image.get_layer_by_name('text'))
	text_bounds = image.get_selection().bounds(image)
	height = text_bounds.y2 - text_bounds.y1
	Gimp.Selection.none(image)
	for x1 in range(-height // 3 * 4, image.get_width(), x_step):
		x2 = x1 + height // 3 * 4
		smudge_line(layer, x1, text_bounds.y2, x2, text_bounds.y1, pressure)

Gimp.progress_init('Running sand writing...')

img = Gimp.get_images()[0]
sand_layer = img.get_layer_by_name('sand')
text_layer = img.get_layer_by_name('text')

# constants / args
base_v = 100
nearest = 5
indent_depth_v = 10
rill_layer_count = 3		# how many layers
spread_incr = 12			# how wide they get

# rill constants
rill_start_v = base_v - indent_depth_v
rill_end_v = base_v + 40
rill_steps = 5
rill_start_width = 20
rill_end_width = 5

outline_growth_factor = 3
outline_shrink_factor = 8
final_base_v = 10
gamma = 1.55
step = 2
initial_range_v = 15
sand_range_v = 40
gaussian_blur_radius = 25
smudge_pressure = 60
smudge_diameter = 300

# 1. Convert to linear color
img.convert_precision(Gimp.Precision.U8_LINEAR)

# 2. Find min, max of sand
Gimp.progress_set_text('Finding min and max intensities...')
low_v, high_v, _, h_data = histogram_minmax(sand_layer, step=step)

Gimp.progress_set_text('Re-leveling...')
# 3. Level sand to 100 and a width of 15
shift_levels_gegl(sand_layer, low_v, high_v, base_v, base_v + initial_range_v)

# 4. Gaussian blur sand layer: x and y of 25
gaussian_blur(sand_layer, gaussian_blur_radius)

# 5. Redo min, max
low_v, high_v, _, h_data = histogram_minmax(sand_layer, step=step)

# 6. Level to 100, width of 40 (a little over 2mm @ 100mm wide)
shift_levels_gegl(sand_layer, low_v, high_v, base_v, base_v + sand_range_v)

# 7. Invert text to white
text_layer.invert(False)

# 8. Make indent layer @ 90
indent_v = base_v - indent_depth_v
indent_layer = copy_layer(text_layer, f"indent - {indent_v}")
shift_levels_gegl(indent_layer, 255, 255, indent_v, indent_v)

# 9. Make white outline of text
outline_layer = copy_layer(text_layer, "outline")
alpha_to_selection(text_layer)
Gimp.Selection.grow(img, outline_growth_factor)
Gimp.context_set_foreground(Gegl.Color.new("white"))
outline_layer.edit_fill(0)
alpha_to_selection(text_layer)
Gimp.Selection.shrink(img, outline_shrink_factor)
outline_layer.edit_clear()
Gimp.Selection.none(img)

# 10. Do rill layers
Gimp.progress_set_text('Adding rill layers...')
spread_layers = []
rill_incr_v = (rill_end_v - rill_start_v) // rill_steps
rill_width_incr = (rill_start_width - rill_end_width) // rill_steps # inverted cuz it's wider deeper
rill_width = rill_start_width
for depth_v in range(rill_start_v, rill_end_v + 1, rill_incr_v):
	l = copy_layer(outline_layer, f"spread - {rill_width} @ {depth_v}")
	shift_levels_gegl(l, 255, 255, depth_v, depth_v)
	spread(l, rill_width)
	spread_layers.append(l)
	rill_width += rill_width_incr

# 11. Hide legacy layers
outline_layer.set_visible(False)
text_layer.set_visible(False)

# 12. Merge visible layers and get new histogram data
img.merge_visible_layers(Gimp.MergeType.EXPAND_AS_NECESSARY)
sand_layer = img.get_layer_by_name('sand')
Gimp.progress_set_text('Finding new min and max intensities...')
new_low_v, new_high_v, _, h_data = histogram_minmax(sand_layer, step=step)

# 13. Add streaks
# TODO: create brush
#         "2. Hardness 100"; Size: 259; Hardness: 50; Force: 25
brush = Gimp.Brush.new('2. Hardness 100')
Gimp.context_set_brush(brush)
Gimp.context_set_brush_size(smudge_diameter)
Gimp.context_set_brush_hardness(0.50)
Gimp.context_set_brush_force(0.25)
Gimp.context_set_brush_spacing(0.10)
smudges(sand_layer, int(smudge_diameter * 0.8), pressure=smudge_pressure)

# 14. Add signature
Gimp.progress_set_text('Adding signature...')
signature = "afiril"
font_size = 128
text_vertical_offset = 75
sig_indent_v = base_v - indent_depth_v

font = Gimp.Font.get_by_name('Sans-serif Bold Italic')
hex_v = format(indent_v, 'x')
Gimp.context_set_foreground(Gegl.Color.new('white'))
extents = Gimp.text_get_extents_font(signature, font_size, font)
x = (img.get_width() - extents.width) / 2
y = img.get_height() - text_vertical_offset - extents.height
signature_layer = Gimp.text_font(img, None, x, y, signature, -1, True, font_size, font)
signature_layer.resize_to_image_size()
sig_glow_layer = copy_layer(signature_layer, 'signature glow', 3)
alpha_to_selection(sig_glow_layer)
Gimp.Selection.grow(img, 15)
Gimp.context_set_foreground(Gegl.Color.new("white"))
sig_glow_layer.edit_fill(0)
glow_v = new_high_v - indent_depth_v
shift_levels_gegl(sig_glow_layer, 255, 255, glow_v, glow_v)
img.merge_down(sig_glow_layer, 0)
Gimp.Selection.none(img)

# we're in linear space and Color.new() only does non-linear, so shift to the desired color instead.
shift_levels_gegl(signature_layer, 255, 255, indent_v, indent_v)
img.merge_down(signature_layer, 0)

# 15. Shift colors to final band and convert to non-linear
sand_layer = img.get_layer_by_name('sand')
shift_levels_gegl(sand_layer, new_low_v, new_high_v, final_base_v, final_base_v + (new_high_v - new_low_v + 1))
img.convert_precision(Gimp.Precision.U8_NON_LINEAR)

# 16. Cleanup
Gimp.progress_set_text('Done.')
Gimp.progress_update(1.0)
Gimp.progress_end()


# A typical design has a range of ~95 "layers" of intensity.
# At 100mm wide, that's ~5.25mm thick.
# That means there are ~18.1 "layers" per mm.
