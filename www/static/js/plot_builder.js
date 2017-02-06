/**
 * Global array of plots.
 * Key   - plot identifier, also used as DOM id.
 * Value - plot object (ChartJS object, options, data ...).
 */
var plots = {};

/**
 * Default options of new plots. Need to redefine at least title.
 * @sa plot_set_title().
 */
var plot_options_default = {
	responsive: true,
	maintainAspectRatio: false,
	title:{
    		display:true,
		text: null
	},
	tooltips: {
		mode: 'index',
		intersect: false,
	},
	hover: {
		mode: 'nearest',
		intersect: true
	},
	scales: {
		xAxes: [{
			display: true,
			scaleLabel: {
				display: true,
				labelString: 'День'
			}
		}],
		yAxes: [{
			display: true,
			scaleLabel: {
				display: true,
				labelString: 'Значение'
			}
		}]
	}
};

/**
 * Create a new plot object with the following structure:
 * {
 * 	'chart': ChartJS object,
 * 	'data': {},
 * 	'triggers_on_update': []
 * 	'options': {},
 * 	'type': 'bubble' or 'line'
 * }
 * Trigger functions are called on each Chart object update
 * and must have the following signature:
 * function (plot_id, control_data).
 * control_data - dictionary of restrictions
 *                (min/max X, min/max Y) that is passed to each
 *                trigger. Trigger can modify control_data object
 *                and next trigger will see changes.
 *                For example, if the first trigger makes
 *
 *                    control_data.some_param = 'value',
 *
 *                then the next trigger will see
 *                control_data with 'some_param' key equal to
 *                'value'.
 * Order of triggers execution is the same as order of addition.
 */
function plot_create(plot_id) {
	if (plot_id in plots) {
		console.log('Broken in plot_create');
		return;
	}
	plots[plot_id] = {
		data: {},
		triggers_on_update: [],
		/*
		 * Clone dictionary to avoid default options
		 * object modification.
		 */
		options: $.extend({}, plot_options_default),
		type: 'line'
	};
}

/**
 * Check if the plot was showed on a page.
 * @param plot_id Identifier of the plot.
 */
function plot_is_showed(plot_id) {
	return plot_id in plots && 'chart' in plots[plot_id];
};

/**
 * Destroy Chart object (visible part of the plot).
 * @param plot_id Identifier of the plot.
 */
function plot_destroy(plot_id) {
	if (! plot_is_showed(plot_id)) {
		console.log('Broken in plot_destroy');
		return;
	}
	plots[plot_id]['chart'].destroy();
	delete plots[plot_id]['chart'];
};

/**
 * Recreate the Chart object, if, for example, the data was
 * modified.
 * @param plot_id Identifier of the plot.
 */
function plot_refresh(plot_id) {
	if (! plot_is_showed(plot_id)) {
		console.log('Broken in plot_refresh');
		return;
	}
	plots[plot_id]['chart'].update();
};

/**
 * Show Chart object on the page.
 * @param plot_id Identifier of the plot.
 */
function plot_show(plot_id) {
	if (! (plot_id in plots)) {
		console.log('Broken in plot_show');
		return;
	}
	var plot = plots[plot_id];
	var dom = document.getElementById(plot_id).getContext("2d");
	plot['chart'] = new Chart(dom, { type: plot.type, data: plot.data,
					 options: plot.options });
};

/**
 * Get max label on Ox line.
 * @param plot_id Identifier of the plot.
 */
function plot_get_x_max(plot_id) {
	if (! plot_is_showed(plot_id)) {
		console.log('Broken in plot_get_x_max');
		return;
	}
	return plots[plot_id]['chart'].scales['x-axis-0'].max;
};

/**
 * Get min label on Ox line.
 * @param plot_id Identifier of the plot.
 */
function plot_get_x_min(plot_id) {
	if (! plot_is_showed(plot_id)) {
		console.log('Broken in plot_get_x_min');
		return;
	}
	return plots[plot_id]['chart'].scales['x-axis-0'].min;
};

/**
 * Get options of the plot.
 * @param plot_id Identifier of the plot.
 */
function plot_options(plot_id) {
	if (! (plot_id in plots)) {
		console.log('Broken in plot_options');
		return;
	}
	return plots[plot_id].options;
}

/**
 * Set label of the Ox line.
 * @param plot_id Identifier of the plot.
 * @param text    Text of the label.
 */
function plot_set_xLabel(plot_id, text) {
	if (! (plot_id in plots)) {
		console.log('Broken in plot_set_xLabel');
		return;
	}
	plot_options(plot_id).scales.xAxes[0].scaleLabel.labelString = text;
};

/**
 * Set label of the Oy line.
 * @param plot_id Identifier of the plot.
 * @param text    Text of the label.
 */
function plot_set_yLabel(plot_id, text) {
	if (! (plot_id in plots)) {
		console.log('Broken in plot_set_yLabel');
		return;
	}
	plot_options(plot_id).scales.yAxes[0].scaleLabel.labelString = text;
};

/**
 * Add a new trigger for event of plot update.
 * @param plot_id Identifier of the plot.
 * @param trigger Function with parameters
 *                (plot_id, control_data), @sa plot_create().
 */
function plot_add_trigger_on_update(plot_id, trigger) {
	if (! (plot_id in plots)) {
		console.log('Broken in plot_add_trigger_on_update');
		return;
	}
	plots[plot_id].triggers_on_update.push(trigger);
};

/**
 * Set title of the plot.
 * @param plot_id Identifier of the plot.
 * @param text    Text of the title.
 */
function plot_set_title(plot_id, text) {
	if (! (plot_id in plots)) {
		console.log('Broken in plot_set_title');
		return;
	}
	plot_options(plot_id).title.text = text;
};

/**
 * Set type of the plot.
 * @param plot_id Identifier of the plot.
 * @param type    Default type of the plot charts: line or bubble.
 *                @sa ChartJS documentation for details.
 */
function plot_set_type(plot_id, type) {
	if (! (plot_id in plots) || (type != 'line' && type != 'bubble')) {
		console.log('Broken in plot_set_type');
		return;
	}
	plots[plot_id].type = type;
};

/**
 * Set labels for Ox line.
 * @param plot_id Identifier of the plot.
 * @param labels  Array of the labels with same size as array
 *                of points.
 */
function plot_set_labels(plot_id, labels) {
	if (! (plot_id in plots)) {
		console.log('Broken in plot_set_labels');
		return;
	}
	plots[plot_id].data.labels = labels;
};

/**
 * Delete all data from the plot.
 * @param plot_id Identifier of the plot.
 */
function plot_clear_data(plot_id) {
	if (! (plot_id in plots)) {
		console.log('Broken in plot_clear_data');
		return;
	}
	plots[plot_id].data.datasets = [];
};

/**
 * Add new dataset to the plot.
 * @param plot_id Identifier of the plot.
 * @parameters    Dictionary with following keys:
 *                data: array of data points,
 *                label: name of the dataset to show to a user,
 *                color: color of the data points,
 *                type: 'bubble' or 'line',
 *                no_points: true, if line must continous
 *                           like ------, not like ---*---*---*,
 *                border_dash: Border dash [x, y] means that line
 *                             will have gaps length Y pixels and
 *                             dashes with X pixels length like:
 *                             ----     ----     ----     ----
 *                              x    y   x    y    x   y    x
 */
function plot_add_data(plot_id, parameters) {
	if (! (plot_id in plots)) {
		console.log('Broken in plot_add_data');
		return;
	}
	var dataset = { fill: false, data: parameters.data };
	if ('label' in parameters)
		dataset.label = parameters.label;
	if ('color' in parameters) {
		dataset.backgroundColor = parameters.color;
		dataset.borderColor = parameters.color;
	}
	if ('type' in parameters)
		dataset.type = parameters.type;
	if ('no_points' in parameters && parameters.no_points) {
		dataset.PointStyle = 'none';
		dataset.radius = 0;
	}
	if ('border_dash' in parameters)
		dataset.borderDash = parameters.border_dash;
	var plot = plots[plot_id];
	if (plot.data.datasets)
		plot.data.datasets.push(dataset);
	else
		plot.data.datasets = [dataset, ];
};

/**
 * Update plot. Usefull to show new data or to update existing
 * datasets.
 * @param plot_id Identifier of the plot.
 */
function update_plot(plot_id) {
	if (! (plot_id in plots)) {
		console.log('Broken in update_plot');
		return;
	}
	var y_min = document.getElementById("plot-y-min").value;
	var y_max = document.getElementById("plot-y-max").value;
	var x_min = document.getElementById("plot-x-min").value;
	var x_max = document.getElementById("plot-x-max").value;
	var param = document.getElementById("plot-param").value;
	var y_ticks = {};
	var x_ticks = {};
	var control_data = {};
	if (y_min != '') {
		y_min = parseFloat(y_min);
		if (y_min != NaN) {
			y_ticks.min = y_min;
			control_data.y_min = y_min;
		}
	}
	if (y_max != '') {
		y_max = parseFloat(y_max);
		if (y_max != NaN) {
			y_ticks.max = y_max;
			control_data.y_max = y_max;
		}
	}
	if (x_min != '') {
		x_min = parseFloat(x_min);
		if (x_min != NaN) {
			x_ticks.min = x_min;
			control_data.x_min = x_min;
		}
	}
	if (x_max != '') {
		x_max = parseFloat(x_max);
		if (x_max != NaN) {
			x_ticks.max = x_max;
			control_data.x_max = x_max;
		}
	}
	var plot = plots[plot_id];
	var options = plot.options;
	options.scales.xAxes[0].ticks = x_ticks;
	options.scales.yAxes[0].ticks = y_ticks;
	for (var i = 0; i < plot.triggers_on_update.length; ++i)
		plot.triggers_on_update[i](plot_id, control_data);
};