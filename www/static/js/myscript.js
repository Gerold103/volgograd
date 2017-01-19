function clear_childs(elem) {
	while (elem.firstChild) {
		elem.removeChild(elem.firstChild);
	}
};

function string_fixed_width(value, need_width) {
	var str = value.toString();
	var diff = need_width - str.length;
	if (diff <= 0)
		return str;
	padding = diff / 2;
	if (diff % 2)
		padding++;
	var spaces = '';
	for (var i = 0; i < padding; ++i) spaces += ' ';
	return spaces + str + spaces;
};
