// place any jQuery/helper plugins in here, instead of separate, slower script files.

$(function() {

    var csrftoken = $('meta[name=csrf-token]').attr('content')

    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken)
            }
        }
    })

    $(function(){
        var hash = window.location.hash;
        hash && $('ul.nav a[href="' + hash + '"]').tab('show');

        $('.nav-tabs a').click(function (e) {
            $(this).tab('show');
            window.location.hash = this.hash;
            $(window).scrollTop(0);
        });

    });

    $(".tagsinput").tagsinput({
        tagClass: "label label-default",
        trimValue: true
    });


    $('.tagsinput').on('itemAdded', function(event) {

        var data = JSON.stringify([]);

        if ($(this).val() != null)
            data = JSON.stringify($(this).tagsinput('items'));

        $.ajax({
            url: $(this).data('uri'),
            contentType: "application/json",
            data: data,
            dataType: "json",
            type: "POST"
        }).done(function (data, textStatus, jqXHR) {
            console.log(jqXHR.status);
        })

    });


    $('.tagsinput').on('itemRemoved', function(event) {

        var data = JSON.stringify([]);

        if ($(this).val() != null)
            data = JSON.stringify($(this).tagsinput('items'));

        $.ajax({
            url: $(this).data('uri'),
            contentType: "application/json",
            data: data,
            dataType: "json",
            type: "POST"
        }).done(function (data, textStatus, jqXHR) {
            console.log(jqXHR.status);
        })

    });


    $(document).on('click', '.js-delete, .glyphicon-trash[data-uri]', function(event) {
        event.preventDefault();

        var $button = $(event.target).closest('.js-delete');
        if (!$button.length) {
            $button = $(event.target).closest('.glyphicon-trash[data-uri]');
        }
        var uri = $button.data('uri') || $button.find('[data-uri]').first().data('uri');

        if (!uri) {
            return false;
        }

        var confirmMessage = $button.data('confirm') || "Вы уверены, что хотите удалить этот элемент? Это действие нельзя отменить.";
        if (!confirm(confirmMessage)) {
            return false;
        }

        var removeTarget = $button.data('removeTarget') || 'tr, .panel';
        var tr = $button.closest(removeTarget);
        var redirectUrl = $button.data('redirect');

        $.ajax({
            url: uri,
            contentType: "application/json",
            type: $button.data('method') || "DELETE"
        }).done(function (data, textStatus, jqXHR) {
            if (tr.length) {
                $(tr).remove();
            }
            if (redirectUrl) {
                window.location.href = redirectUrl;
            }
            console.log(jqXHR.status);
        }).fail(function (jqXHR) {
            var message = "Не удалось удалить элемент.";
            if (jqXHR.status) {
                message += " Код ошибки: " + jqXHR.status + ".";
            }
            alert(message);
        })

    })

    $('.activate-node').on('click', function(event) {
         if ($(this).data('uri') == null || $(this).data('uri') == "")
            return;

        var el = $(this);
        var icon = el.find('i');
        var is_active = icon.hasClass('fa-square-o') || el.hasClass('glyphicon-unchecked') || null;

        $.post($(this).data('uri'), {
            is_active: is_active
        }).done(function (data, textStatus, jqXHR) {
            icon.toggleClass('fa-check-square-o fa-square-o');
            el.toggleClass('glyphicon-check glyphicon-unchecked');
        });

    })

    $('body').scrollspy({
        target: '.bs-docs-sidebar',
        offset: 70
    })

    $('#sidebar').affix({
        offset: {
            top: 0
        }
    })

    // --------------------------------------------------------------------------------

    var $queryBuilder = $('#query-builder');

    if ($queryBuilder.length) {
        var QueryBuilder = $.fn.queryBuilder.constructor;

        var SUPPORTED_OPERATOR_NAMES = [
            'equal',
            'not_equal',
            'begins_with',
            'not_begins_with',
            'contains',
            'not_contains',
            'ends_with',
            'not_ends_with',
            'is_empty',
            'is_not_empty',
            'less',
            'less_or_equal',
            'greater',
            'greater_or_equal',
        ];

        var SUPPORTED_OPERATORS = SUPPORTED_OPERATOR_NAMES.map(function (operator) {
            return QueryBuilder.OPERATORS[operator];
        });

        var COLUMN_OPERATORS = SUPPORTED_OPERATOR_NAMES.map(function (operator) {
            return {
                type: 'column_' + operator,
                nb_inputs: QueryBuilder.OPERATORS[operator].nb_inputs + 1,
                multiple: true,
                apply_to: ['string'],        // Currently, all column operators are strings
            };
        });

        var SUPPORTED_COLUMN_OPERATORS = SUPPORTED_OPERATOR_NAMES.map(function (operator) {
            return 'column_' + operator;
        });

        // Copy existing names
        var CUSTOM_LANG = {};
        SUPPORTED_OPERATOR_NAMES.forEach(function (op) {
            CUSTOM_LANG['column_' + op] = QueryBuilder.regional.en.operators[op];
        });

        // Custom operators
        Array.prototype.push.apply(SUPPORTED_OPERATOR_NAMES, ['matches_regex', 'not_matches_regex']);
        Array.prototype.push.apply(SUPPORTED_OPERATORS, [
            {
                type: 'matches_regex',
                nb_inputs: 1,
                multiple: true,
                apply_to: ['string'],
            },
            {
                type: 'not_matches_regex',
                nb_inputs: 1,
                multiple: true,
                apply_to: ['string'],
            },
        ]);
        CUSTOM_LANG['matches_regex'] = 'matches regex';
        CUSTOM_LANG['not_matches_regex'] = "doesn't match regex";

        Array.prototype.push.apply(SUPPORTED_COLUMN_OPERATORS, ['column_matches_regex', 'column_not_matches_regex']);
        Array.prototype.push.apply(COLUMN_OPERATORS, [
            {
                type: 'column_matches_regex',
                nb_inputs: 2,
                multiple: true,
                apply_to: ['string'],
            },
            {
                type: 'column_not_matches_regex',
                nb_inputs: 2,
                multiple: true,
                apply_to: ['string'],
            },
        ]);
        CUSTOM_LANG['column_matches_regex'] = 'matches regex';
        CUSTOM_LANG['column_not_matches_regex'] = "doesn't match regex";

        // Get existing rules, if any.
        var existingRules;
        try {
            var v = $('#rules-hidden').val();
            if (v) {
                existingRules = JSON.parse(v);
            }
        } catch (e) {
            // Do nothing.
        }

        $queryBuilder.queryBuilder({
            filters: [
                {
                    id: 'query_name',
                    type: 'string',
                    label: 'Название запроса',
                    operators: SUPPORTED_OPERATOR_NAMES,
                },
                {
                    id: 'action',
                    type: 'string',
                    label: 'Действие',
                    operators: SUPPORTED_OPERATOR_NAMES,
                },
                {
                    id: 'host_identifier',
                    type: 'string',
                    label: 'Идентификатор хоста',
                    operators: SUPPORTED_OPERATOR_NAMES,
                },
                {
                    id: 'timestamp',
                    type: 'integer',
                    label: 'Время',
                    operators: SUPPORTED_OPERATOR_NAMES,
                },
                {
                    id: 'column',
                    type: 'string',
                    label: 'Колонка',
                    operators: SUPPORTED_COLUMN_OPERATORS,
                    placeholder: 'значение',
                },
            ],

            operators: SUPPORTED_OPERATORS.concat(COLUMN_OPERATORS),

            lang: {
                operators: CUSTOM_LANG,
            },

            plugins: {
                'bt-tooltip-errors': {
                    delay: 100,
                    placement: 'bottom',
                },
                'sortable': {
                    icon: 'glyphicon glyphicon-move',
                },
            },

            // Existing rules (if any)
            rules: existingRules,
        });

        // Set the placeholder of the first value for all 'column_*' rules to
        // 'column name'.  A bit hacky, but this seems to be the only way to
        // accomplish this.
        $queryBuilder.on('getRuleInput.queryBuilder.filter', function (evt, rule, name) {
            if (rule.operator.type.match(/^column_/) && name.match(/value_0$/)) {
                var el = $(evt.value);
                $(el).attr('placeholder', 'имя колонки');;
                evt.value = el[0].outerHTML;
            }
        });

        $('#submit-button').on('click', function(e) {
          var $builder = $queryBuilder;

          if (!$builder) {
            return true;
          }

          if (!$builder.queryBuilder('validate')) {
            e.preventDefault();
            return false;
          }

          var rules = JSON.stringify($builder.queryBuilder('getRules'));
          $('#rules-hidden').val(rules);
          return true;
        });
    }

})
