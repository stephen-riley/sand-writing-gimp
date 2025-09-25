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

def minmax(drawable):
	for lo in range(0, 256):
		_, _, _, _, pixels, count, _ = drawable.histogram(Gimp.HistogramChannel.VALUE, 0.0, lo / 255.0)
		if count > (pixels * 0.001):
			break
	for hi in range(255, -1, -1):
		_, _, _, _, pixels, count, _ = drawable.histogram(Gimp.HistogramChannel.VALUE, hi / 255.0, 1.0)
		if count > (pixels * 0.001):
			break	
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

def get_density(drawable, low, high):
	_, _, _, _, pixels, count, _ = drawable.histogram(Gimp.HistogramChannel.VALUE, low / 255.0, high / 255.0)
	# print(f"pixels={pixels}, count={count}")
	return pixels, count

def find_color_lower_bound(drawable, epsilon=0.04):
	high = 255
	low = 0
	counter = 0
	min, _ = get_density(drawable, 0, 255)
	min = min * epsilon
	while True:
		counter = counter + 1
		if counter > 9: break
		center = int((high + low) / 2)
		_, lhalf = get_density(drawable, low, center)
		_, hhalf = get_density(drawable, center + 1, high)
		print(f"{low} / {center} / {high}: {int(lhalf)}-{int(hhalf)}")
		if lhalf < min:
			low = center + 1
		elif hhalf < min:
			high = center
		else:
			break
	return low

def find_color_upper_bound(drawable, lower, epsilon=0.04):
	high = 255
	low = lower
	counter = 0
	total_pixels, _ = get_density(drawable, 0, 255)
	min = total_pixels * epsilon
	max = total_pixels - min
	while True:
		if low == high:
			return low
		counter = counter + 1
		if counter > 9: break
		center = int((high + low) / 2)
		_, lhalf = get_density(drawable, low, center)
		_, hhalf = get_density(drawable, center + 1, high)
		print(f"{low} / {center} / {high}: {(lhalf)}-{(hhalf)}")
		if lhalf > hhalf:
			high = center
		elif hhalf > lhalf:
			low = center + 1
		else:
			break
	return high

def minmax2(drawable):
	for lo in range(0, 256):
		_, _, _, _, pixels, count, _ = drawable.histogram(Gimp.HistogramChannel.VALUE, 0.0, lo / 255.0)
		if count > (pixels * 0.001):
			break
			
	for hi in range(255, -1, -1):
		_, _, _, _, pixels, count, _ = drawable.histogram(Gimp.HistogramChannel.VALUE, hi / 255.0, 1.0)
		if count > (pixels * 0.001):
			break
	
	print(f"low/high: {lo}/{hi}")
	return lo, hi