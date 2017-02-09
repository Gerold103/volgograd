/**
 * Global array of plots.
 * Key   - plot identifier, also used as DOM id.
 * Value - plot object (ChartJS object, options, data ...).
 */
var plots = {};

/**
 * Default options for new plots. You need to redefine at least
 * title - @sa plot_set_title().
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
 * 	chart:   ChartJS object,
 * 	data:    {},
 * 	options: {},
 *
 * 	Default is 'line', for redefine @sa plot_set_type().
 * 	type: 'bubble' or 'line',
 *
 * 	For details of the params_config see text below.
 * 	params_config: {},
 *
 * 	List of parameter names, that need to show on the plot.
 * 	Names must be from params_config.
 * 	parameters_to_show: [],
 *
 * 	triggers_on_update:       [],
 * 	triggers_dataset_created: [],
 * 	triggers_show_started:    [],
 * 	triggers_show_finished:   [],
 * 	get_title:    function(plot_id, control_data),
 * 	get_x_values: function(plot_id, control_data)
 * }
 * Triggers on update are called on each Chart object update and
 * must have the following signature:
 *
 * 		function (plot_id, control_data).
 *
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
 * If the trigger returns 'false' then triggers execution is
 * stopped.
 *
 * Triggers on dataset created are called for each dataset created
 * for showing and must have the following signature:
 *
 * 		function(param_name, dataset).
 *
 * param_name - name of the parameter from params_config,
 * dataset    - data to show. In the triggers you can, for
 *              example, sort data of the dataset before showing.
 *
 * Triggers on show started are called on each show of the plot
 * and must have the following signature:
 *
 * 		function(plot_id, control_data).
 *
 * In these triggers you can, for example, download from the
 * server necessary parameters. If at least one trigger returns
 * false then the plot will not be showed and other triggers will
 * not be called.
 *
 * Triggers on show finished are called on each finish of plot
 * show and must have the following signature:
 *
 * 		function(plot_id, control_data).
 *
 * In these triggers you can, for example, add some points to
 * the plot after it was showed.
 *
 * Params configuration is a dictionary with the following format:
 * {
 * 	Any name of parameter to show.
 * 	name: {
 * 		Human readable name.
 *		title: title,
 *
 * 		Type of the parameters: 'set' or 'parameter'.
 * 		Default is 'parameter'.
 *		type: parameter, set,
 *
 * 		True if the parameter is part of a set of
 * 		parameters. Default is false.
 *		is_child: true or false
 *
 *		Parameters part:
 *			@sa plot_add_data().
 *			border_dash: [len, gap],
 *
 * 			Text to show on the heading of the plot.
 * 			Default equal to title.
 *			plot_label: label,
 *
 * 			@sa plot_add_data().
 *			plot_type: 'line' or 'bubble',
 *
 * 			Function to get parameter value.
 * 			If returns null then nothing is added to
 * 			the dataset. If returns NaN or
 * 			{ x: ..., y: ... } then the new point is
 * 			added to the dataset.
 *			get_value: function(name, x),
 *
 * 			Color of the plot of this parameter.
 *			color: color,
 *
 * 			@sa plot_add_data().
 * 			no_points: true or false
 *
 *		Set part:
 *			List of names of childs.
 *			childs: [name1, name2, ..., nameN]
 *	},
 *	...
 * }
 */
function plot_create(plot_id, params_config, get_title, get_x_values) {
	if (plot_id in plots) {
		console.log('Broken plot_create');
		return;
	}
	plots[plot_id] = {
		data: {},
		/*
		 * Clone dictionary to avoid default options
		 * object modification.
		 */
		options: $.extend({}, plot_options_default),
		type: 'line',
		params_config: params_config,
		parameters_to_show: [],
		triggers_on_update: [],
		triggers_dataset_created: [],
		triggers_show_started: [],
		triggers_show_finished: [],
		get_title: get_title,
		get_x_values: get_x_values
	};
};

function plot_update_parameters_to_show(plot_id, parameters) {
	if (! (plot_id in plots)) {
		console.log('Broken plot_create');
		return;
	}
	plots[plot_id].parameters_to_show = parameters;
};

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
		console.log('Broken plot_destroy');
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
		console.log('Broken plot_refresh');
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
		console.log('Broken plot_show');
		return;
	}
	var dom = document.getElementById(plot_id).getContext("2d");
	var plot = plots[plot_id];
	plot['chart'] = new Chart(dom, { type: plot.type, data: plot.data,
					 options: plot.options });
};

/**
 * Get max label on Ox line.
 * @param plot_id Identifier of the plot.
 */
function plot_get_x_max(plot_id) {
	if (! plot_is_showed(plot_id)) {
		console.log('Broken plot_get_x_max');
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
		console.log('Broken plot_get_x_min');
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
		console.log('Broken plot_options');
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
		console.log('Broken plot_set_xLabel');
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
		console.log('Broken plot_set_yLabel');
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
		console.log('Broken plot_add_trigger_on_update');
		return;
	}
	plots[plot_id].triggers_on_update.push(trigger);
};

/**
 * Add a new trigger for event of dataset created.
 * @param plot_id Identifier of the plot.
 * @param trigger Function with parameters
 *                (param_name, param_id, dataset),
 *                @sa plot_create().
 */
function plot_add_trigger_dataset_created(plot_id, trigger) {
	if (! (plot_id in plots)) {
		console.log('Broken plot_add_trigger_dataset_created');
		return;
	}
	plots[plot_id].triggers_dataset_created.push(trigger);
};

/**
 * Add a new trigger for event of show started.
 * @param plot_id Identifier of the plot.
 * @param trigger Function with parameters
 *                function(plot_id, control_data), @sa plot_create().
 */
function plot_add_trigger_show_started(plot_id, trigger) {
	if (! (plot_id in plots)) {
		console.log('Broken plot_add_trigger_show_started');
		return;
	}
	plots[plot_id].triggers_show_started.push(trigger);
};


/**
 * Add a new trigger for event of show finished.
 * @param plot_id Identifier of the plot.
 * @param trigger Function with parameters
 *                function(plot_id, control_data), @sa plot_create().
 */
function plot_add_trigger_show_finished(plot_id, trigger) {
	if (! (plot_id in plots)) {
		console.log('Broken plot_add_trigger_show_finished');
		return;
	}
	plots[plot_id].triggers_show_finished.push(trigger);
};

/**
 * Set title of the plot.
 * @param plot_id Identifier of the plot.
 * @param text    Text of the title.
 */
function plot_set_title(plot_id, text) {
	if (! (plot_id in plots)) {
		console.log('Broken plot_set_title');
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
		console.log('Broken plot_set_type');
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
		console.log('Broken plot_set_labels');
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
		console.log('Broken plot_clear_data');
		return;
	}
	plots[plot_id].data.datasets = [];
};

/**
 * Get array of datasets.
 * @param plot_id Identifier of the plot.
 */
function plot_get_datasets(plot_id) {
	if (! (plot_id in plots)) {
		console.log('Broken plot_get_datasets');
		return;
	}
	return plots[plot_id].data.datasets;
}

/**
 * Add new dataset to the plot.
 * @param plot_id Identifier of the plot.
 * @parameters    Dictionary with following keys:
 *                data: array of data points,
 *                label: name of the dataset to show to a user,
 *                color: color of the data points,
 *                type: 'bubble' or 'line',
 *                no_points: true, if line must continous
 *                           like --------, not like ---*---*---*,
 *                border_dash: Border dash [x, y] means that line
 *                             will have gaps length Y pixels and
 *                             dashes with X pixels length like:
 *                             ----     ----     ----     ----
 *                              x    y   x    y    x   y    x
 */
function plot_add_data(plot_id, dataset) {
	if (! (plot_id in plots)) {
		console.log('Broken plot_add_data');
		return;
	}
	dataset.fill = false;
	if ('color' in dataset) {
		dataset.backgroundColor = dataset.color;
		dataset.borderColor = dataset.color;
	}
	if ('no_points' in dataset && dataset.no_points) {
		dataset.PointStyle = 'none';
		dataset.radius = 0;
	}
	if ('border_dash' in dataset)
		dataset.borderDash = dataset.border_dash;
	var plot = plots[plot_id];
	if (plot.data.datasets)
		plot.data.datasets.push(dataset);
	else
		plot.data.datasets = [dataset, ];
};

/**
 * Fill the plot with values of the specified parameters and show
 * on the page. Works as trigger_on_update of the plot object.
 * If you want to use this funtion, you must call:
 *
 * 	plot_add_trigger_on_update(plot_id, show_plot);
 */
function show_plot(plot_id, control_data) {
	if (! (plot_id in plots)) {
		console.log('Broken show_plot');
		return false;
	}
	var plot = plots[plot_id];
	for (var i = 0; i < plot.triggers_show_started.length; ++i)
		if (! plot.triggers_show_started[i](plot_id, control_data))
			return false;

	if (plot_is_showed(plot_id))
		plot_destroy(plot_id);
	plot_clear_data(plot_id);
	plot_set_title(plot_id, plot.get_title(plot_id, control_data));

	var x_axes = plot.get_x_values(plot_id, control_data);
	for (var i = 0; i < plot.parameters_to_show.length; ++i) {
		param_name = plot.parameters_to_show[i];
		conf = plot.params_config[param_name];
		var dataset = {};
		var values = [];
		for (var j = 0; j < x_axes.length; ++j) {
			var val = conf.get_value(param_name, x_axes[j]);
			if (val == null)
				continue;
			if (val != val)
				values.push(NaN);
			else
				values.push(val);
		}
		dataset.data = values;
		if (! ('plot_label' in conf))
			dataset.label = conf.title;
		else
			dataset.label = conf.plot_label;
		if ('color' in conf)
			dataset.color = conf.color;
		if ('plot_type' in conf)
			dataset.type = conf.plot_type;
		if ('border_dash' in conf)
			dataset.border_dash = conf.border_dash;
		if ('no_points' in conf && conf.no_points)
			dataset.no_points = conf.no_points;

		var len = plot.triggers_dataset_created.length;
		for (var j = 0; j < len; ++j) {
			var tr = plot.triggers_dataset_created[j];
			if (! tr(param_name, dataset))
				break;
		}
		plot_add_data(plot_id, dataset);
	}
	plot_show(plot_id);

	for (var i = 0; i < plot.triggers_show_finished.length; ++i) {
		var tr = plot.triggers_show_finished[i];
		if (! tr(plot_id, control_data))
			return false;
	}
	return true;
};

/**
 * Update plot. Usefull to show new data or to update existing
 * datasets. You can call this function to build the new plot or
 * to update the existing one.
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
	for (var i = 0; i < plot.triggers_on_update.length; ++i) {
		if (! plot.triggers_on_update[i](plot_id, control_data))
			break;
	}
};
