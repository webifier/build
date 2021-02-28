{% extends 'full.tpl' %}

{% block html_head %}
	{{ super() }}
<script src="https://code.jquery.com/jquery-3.4.1.min.js"
	integrity="sha256-CSXorXvZcTkaix6Yvo6HppcZGetbYMGWSFlBw8HfCJo="
	crossorigin="anonymous"></script>

<script>
$(document).ready(function() {          
    $('.code_shower').on('click',function(){
	var header = $(this);
	var codecell = $(this).next()
        codecell.slideToggle(0, function() {
		if (codecell.is(':hidden')) {
			header.text("Show Code");
			header.css("border-radius", "2px 2px 2px 2px");
		} else {
			header.text("Hide Code");
			header.css("border-radius", "2px 2px 0px 0px")
		}
	});
    });
    $('.hidden_default').next().hide();
});
</script>

<style>
div.input {
	flex-direction: column !important;
}
div.input_area {
	border-radius: 0px 0px 2px 2px;
}
div.code_shower {
	background: lightgray;
	padding: 5px 10px;
	cursor: pointer;
	border-radius: 2px 2px 0px 0px;
}
</style>
{% endblock html_head %}

{% block input %}
{% if 'code_shown' in cell['metadata'].get('tags', []) %}
	<div class="code_shower">Hide Code</div>
{% else %}
    	<div class="code_shower hidden_default">Show Code</div>
{% endif %}

{{ super() }}
{% endblock input %}

{% block output_prompt %}
{% endblock output_prompt %}

{% block in_prompt %}
{% endblock in_prompt %}