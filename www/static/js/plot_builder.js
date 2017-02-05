function get_plot_DOM() {
	return document.getElementById("plot").getContext("2d");
};

function get_plot_object() {
	return window.myPlot;
};

function plot_is_created() {
	return 'myPlot' in window;
};

function plot_object_set(ob) {
	window.myPlot = ob;
};

var plot_data = {};
var plot_builder = null;
var plot_builder = null;
var plot_param_reader = null;

var plot_options = {
	responsive: true,
	maintainAspectRatio: false,
	title:{
    		display:true,
    		text:'Среднесуточная температура, факт. Т1'
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

function plot_get_x_max() {
	return get_plot_object().scales['x-axis-0'].max;
};

function plot_get_x_min() {
	return get_plot_object().scales['x-axis-0'].min;
};

function plot_set_xLabel(text) {
	plot_options.scales.xAxes[0].scaleLabel.labelString = text;
};

function plot_set_yLabel(text) {
	plot_options.scales.yAxes[0].scaleLabel.labelString = text;
};

function plot_set_builder(builder) {
	plot_builder = builder;
};

function plot_set_param_reader(reader) {
	plot_param_reader = reader;
};

function plot_set_title(text) {
	plot_options.title.text = text;
};

function plot_set_labels(labels) {
	plot_data.labels = labels;
};

function plot_clear_data() {
	plot_data.datasets = [];
};

function plot_add_data(parameters) {
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
	if (plot_data.datasets)
		plot_data.datasets.push(dataset);
	else
		plot_data.datasets = [dataset, ];
};

function update_plot() {
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
	plot_options.scales.xAxes[0].ticks = x_ticks;
	plot_options.scales.yAxes[0].ticks = y_ticks;

	if (plot_param_reader)
		plot_param_reader(control_data);
	if (plot_builder)
		plot_builder(control_data);
};