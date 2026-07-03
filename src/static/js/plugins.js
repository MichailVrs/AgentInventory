// place any jQuery/helper plugins in here, instead of separate, slower script files.

(function($) {
    if (!$ || $.fn.DataTable) {
        return;
    }

    function optionText(language, key, fallback) {
        return language && language[key] ? language[key] : fallback;
    }

    function normalizeLengths(lengthMenu, selected) {
        var values = [10, 25, 50, 100];

        if ($.isArray(lengthMenu)) {
            if ($.isArray(lengthMenu[0])) {
                values = lengthMenu[0];
            } else {
                values = lengthMenu;
            }
        }

        if ($.inArray(selected, values) === -1) {
            values.push(selected);
        }

        return $.grep(values, function(value, index) {
            return value && $.inArray(value, values) === index;
        }).sort(function(a, b) {
            return a - b;
        });
    }

    function renderLengthControl(text, select) {
        var parts = text.split('_MENU_');
        var label = $('<label></label>');

        label.append(document.createTextNode(parts[0] || ''));
        label.append(select);
        label.append(document.createTextNode(parts[1] || ''));

        return label;
    }

    $.fn.DataTable = function(options) {
        options = options || {};
        var language = options.language || {};

        return this.each(function() {
            var table = $(this);
            var tbody = table.find('tbody');
            var rows = tbody.find('tr').not('.dataTables_empty').toArray();
            var pageLength = parseInt(options.pageLength || 10, 10);
            var page = 0;
            var search = '';
            var sortIndex = null;
            var sortDirection = 1;
            var emptyRow = null;

            table.addClass('dataTable no-footer');
            table.wrap('<div class="dataTables_wrapper form-inline dt-bootstrap no-footer"></div>');

            var wrapper = table.parent();
            var top = $('<div class="row"></div>');
            var bottom = $('<div class="row"></div>');
            var lengthCol = $('<div class="col-sm-6"></div>');
            var filterCol = $('<div class="col-sm-6"></div>');
            var infoCol = $('<div class="col-sm-5"></div>');
            var pageCol = $('<div class="col-sm-7"></div>');
            var lengthBox = $('<div class="dataTables_length"></div>');
            var filterBox = $('<div class="dataTables_filter"></div>');
            var infoBox = $('<div class="dataTables_info" role="status" aria-live="polite"></div>');
            var pageBox = $('<div class="dataTables_paginate paging_simple_numbers"></div>');

            var select = $('<select class="form-control input-sm"></select>');
            $.each(normalizeLengths(options.lengthMenu, pageLength), function(_, value) {
                select.append($('<option></option>').attr('value', value).text(value));
            });
            select.val(pageLength);

            lengthBox.append(renderLengthControl(
                optionText(language, 'lengthMenu', 'Show _MENU_ entries'),
                select
            ));

            var searchInput = $('<input type="search" class="form-control input-sm">');
            filterBox.append(
                $('<label></label>')
                    .append(document.createTextNode(optionText(language, 'search', 'Search:') + ' '))
                    .append(searchInput)
            );

            top.append(lengthCol.append(lengthBox));
            top.append(filterCol.append(filterBox));
            bottom.append(infoCol.append(infoBox));
            bottom.append(pageCol.append(pageBox));
            wrapper.prepend(top);
            wrapper.append(bottom);

            function rowText(row) {
                return $(row).text().toLowerCase();
            }

            function filteredRows() {
                var visible = $.grep(rows, function(row) {
                    return !search || rowText(row).indexOf(search) !== -1;
                });

                if (sortIndex !== null) {
                    visible.sort(function(a, b) {
                        var aText = $.trim($(a).children().eq(sortIndex).text()).toLowerCase();
                        var bText = $.trim($(b).children().eq(sortIndex).text()).toLowerCase();
                        return aText.localeCompare(bText) * sortDirection;
                    });
                }

                return visible;
            }

            function textWithStats(template, start, end, total, max) {
                return template
                    .replace('_START_', start)
                    .replace('_END_', end)
                    .replace('_TOTAL_', total)
                    .replace('_MAX_', max);
            }

            function addPageButton(list, text, targetPage, disabled, active) {
                var item = $('<li></li>');
                var link = $('<a href="#"></a>').text(text);

                if (disabled) {
                    item.addClass('disabled');
                }
                if (active) {
                    item.addClass('active');
                }

                link.on('click', function(event) {
                    event.preventDefault();
                    if (!disabled && !active) {
                        page = targetPage;
                        render();
                    }
                });

                item.append(link);
                list.append(item);
            }

            function renderPagination(totalPages) {
                var labels = language.paginate || {};
                var list = $('<ul class="pagination"></ul>');
                var startPage = Math.max(0, page - 2);
                var endPage = Math.min(totalPages - 1, page + 2);

                addPageButton(list, labels.first || 'First', 0, page === 0, false);
                addPageButton(list, labels.previous || 'Previous', page - 1, page === 0, false);

                if (startPage > 0) {
                    addPageButton(list, '1', 0, false, page === 0);
                    if (startPage > 1) {
                        list.append('<li class="disabled"><a href="#">...</a></li>');
                    }
                }

                for (var index = startPage; index <= endPage; index++) {
                    addPageButton(list, String(index + 1), index, false, page === index);
                }

                if (endPage < totalPages - 1) {
                    if (endPage < totalPages - 2) {
                        list.append('<li class="disabled"><a href="#">...</a></li>');
                    }
                    addPageButton(list, String(totalPages), totalPages - 1, false, page === totalPages - 1);
                }

                addPageButton(list, labels.next || 'Next', page + 1, page >= totalPages - 1, false);
                addPageButton(list, labels.last || 'Last', totalPages - 1, page >= totalPages - 1, false);

                pageBox.empty().append(list);
            }

            function render() {
                var visible = filteredRows();
                var total = rows.length;
                var filtered = visible.length;
                var effectiveLength = pageLength > 0 ? pageLength : Math.max(filtered, 1);
                var totalPages = Math.max(1, Math.ceil(filtered / effectiveLength));
                var startIndex;
                var endIndex;

                if (page >= totalPages) {
                    page = totalPages - 1;
                }

                startIndex = page * effectiveLength;
                endIndex = Math.min(startIndex + effectiveLength, filtered);

                if (emptyRow) {
                    emptyRow.remove();
                    emptyRow = null;
                }

                $(rows).hide();
                $.each(visible.slice(startIndex, endIndex), function(_, row) {
                    tbody.append(row);
                    $(row).show();
                });

                if (!filtered) {
                    emptyRow = $('<tr class="dataTables_empty"></tr>').append(
                        $('<td></td>')
                            .attr('colspan', table.find('thead th').length || 1)
                            .text(total ? optionText(language, 'zeroRecords', 'No matching records found') : optionText(language, 'emptyTable', 'No data available in table'))
                    );
                    tbody.append(emptyRow);
                }

                if (!filtered) {
                    infoBox.text(optionText(language, 'infoEmpty', 'Showing 0 to 0 of 0 entries'));
                } else {
                    var infoText = textWithStats(
                        optionText(language, 'info', 'Showing _START_ to _END_ of _TOTAL_ entries'),
                        startIndex + 1,
                        endIndex,
                        filtered,
                        total
                    );

                    if (search && filtered !== total) {
                        infoText += ' ' + textWithStats(optionText(language, 'infoFiltered', '(filtered from _MAX_ total entries)'), startIndex + 1, endIndex, filtered, total);
                    }
                    infoBox.text(infoText);
                }

                renderPagination(totalPages);
            }

            select.on('change', function() {
                pageLength = parseInt($(this).val(), 10);
                page = 0;
                render();
            });

            searchInput.on('input', function() {
                search = $.trim($(this).val()).toLowerCase();
                page = 0;
                render();
            });

            table.find('thead th').each(function(index) {
                $(this).css('cursor', 'pointer').on('click', function() {
                    if (sortIndex === index) {
                        sortDirection = -sortDirection;
                    } else {
                        sortIndex = index;
                        sortDirection = 1;
                    }
                    page = 0;
                    render();
                });
            });

            render();
        });
    };
})(window.jQuery);

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

    var knownTags = null;
    var knownTagCallbacks = [];

    function normalizeTag(value) {
        return $.trim(value || '');
    }

    function uniqueTags(values) {
        var seen = {};
        var result = [];

        $.each(values || [], function(_, value) {
            var tag = normalizeTag(value);
            var key = tag.toLowerCase();

            if (tag && !seen[key]) {
                seen[key] = true;
                result.push(tag);
            }
        });

        return result.sort(function(a, b) {
            return a.localeCompare(b);
        });
    }

    function loadKnownTags(callback) {
        if (knownTags !== null) {
            callback(knownTags.slice());
            return;
        }

        knownTagCallbacks.push(callback);
        if (knownTagCallbacks.length > 1) {
            return;
        }

        $.ajax({
            url: "/manage/tags",
            dataType: "json",
            type: "GET",
            headers: {
                "X-Requested-With": "XMLHttpRequest"
            }
        }).done(function(data) {
            knownTags = uniqueTags(data && data.tags ? data.tags : []);
        }).fail(function() {
            knownTags = [];
        }).always(function() {
            var callbacks = knownTagCallbacks.slice();
            knownTagCallbacks = [];
            $.each(callbacks, function(_, done) {
                done(knownTags.slice());
            });
        });
    }

    function rememberTags(tags) {
        knownTags = uniqueTags((knownTags || []).concat(tags || []));
    }

    function readTags($source) {
        var values = [];

        if ($source.is('select')) {
            $source.find('option:selected').each(function() {
                values.push($(this).val());
            });

            if (!values.length) {
                $source.find('option').each(function() {
                    values.push($(this).val());
                });
            }
        } else {
            values = ($source.val() || '').split(/[\n,]+/);
        }

        return uniqueTags(values);
    }

    function writeTags($source, tags) {
        if ($source.is('select')) {
            $source.empty();
            $.each(tags, function(_, tag) {
                $('<option></option>')
                    .attr('value', tag)
                    .prop('selected', true)
                    .text(tag)
                    .appendTo($source);
            });
        } else if ($source.is('textarea')) {
            $source.val(tags.join('\n'));
        } else {
            $source.val(tags.join(','));
        }
    }

    function initTagPicker(source) {
        var $source = $(source);
        var tags = readTags($source);
        var saveTimer = null;
        var pendingRequest = null;

        if ($source.data('tag-picker-ready')) {
            return;
        }
        $source.data('tag-picker-ready', true);

        var placeholder = $source.attr('placeholder') || 'Введите метку';
        var $picker = $('<div class="tag-picker"></div>');
        var $selected = $('<div class="tag-picker-selected"></div>');
        var $control = $('<div class="tag-picker-control"></div>');
        var $input = $('<input type="text" class="tag-picker-input" autocomplete="off">').attr('placeholder', placeholder);
        var $toggle = $('<button type="button" class="tag-picker-toggle" aria-label="Показать метки"><i class="fa fa-caret-down"></i></button>');
        var $menu = $('<div class="tag-picker-menu"></div>').appendTo('body');
        var eventNamespace = '.tagPicker' + Math.random().toString(36).slice(2);

        $control.append($input, $toggle);
        $picker.append($selected, $control);
        $source.after($picker).hide();

        function containsTag(value) {
            var key = normalizeTag(value).toLowerCase();
            var found = false;

            $.each(tags, function(_, tag) {
                if (tag.toLowerCase() === key) {
                    found = true;
                    return false;
                }
            });

            return found;
        }

        function setTags(nextTags, options) {
            tags = uniqueTags(nextTags);
            rememberTags(tags);
            writeTags($source, tags);
            renderSelected();
            renderMenu();
            $source.trigger('change');

            if (!options || !options.silent) {
                saveTags();
            }
        }

        function addTag(value) {
            var tag = normalizeTag(value);

            if (!tag || containsTag(tag)) {
                return;
            }

            tags.push(tag);
            $input.val('');
            setTags(tags);
        }

        function removeTag(value) {
            var key = normalizeTag(value).toLowerCase();
            setTags($.grep(tags, function(tag) {
                return tag.toLowerCase() !== key;
            }));
        }

        function saveTags() {
            var uri = $source.data('uri');

            if (!uri) {
                return;
            }

            clearTimeout(saveTimer);
            saveTimer = setTimeout(function() {
                if (pendingRequest && pendingRequest.readyState !== 4) {
                    pendingRequest.abort();
                }

                pendingRequest = $.ajax({
                    url: uri,
                    contentType: "application/json",
                    data: JSON.stringify(tags),
                    dataType: "json",
                    type: "POST"
                }).fail(function(jqXHR, textStatus) {
                    if (textStatus !== 'abort') {
                        alert('Не удалось сохранить метки. Обновите страницу и попробуйте снова.');
                    }
                });
            }, 150);
        }

        function renderSelected() {
            $selected.empty();

            if (!tags.length) {
                $selected.append('<span class="tag-picker-empty">Метки не выбраны</span>');
                return;
            }

            $.each(tags, function(_, tag) {
                var $badge = $('<span class="tag-picker-badge"></span>');
                var $remove = $('<button type="button" class="tag-picker-remove" aria-label="Удалить метку">&times;</button>');

                $remove.on('click', function() {
                    removeTag(tag);
                    $input.focus();
                });

                $badge.append($('<span></span>').text(tag), $remove);
                $selected.append($badge);
            });
        }

        function renderMenu() {
            var filter = normalizeTag($input.val()).toLowerCase();
            var visible = $.grep(knownTags || [], function(tag) {
                return !filter || tag.toLowerCase().indexOf(filter) !== -1;
            });

            $menu.empty();
            $menu.append('<div class="tag-picker-menu-title">Существующие метки</div>');

            if (visible.length) {
                $.each(visible, function(_, tag) {
                    var id = 'tag-picker-' + Math.random().toString(36).slice(2);
                    var $row = $('<label class="tag-picker-option"></label>');
                    var $checkbox = $('<input type="checkbox">').attr('id', id).prop('checked', containsTag(tag));

                    $checkbox.on('change', function() {
                        if (this.checked) {
                            addTag(tag);
                        } else {
                            removeTag(tag);
                        }
                    });

                    $row.append($checkbox, $('<span></span>').text(tag));
                    $menu.append($row);
                });
            } else {
                $menu.append('<div class="tag-picker-no-options">Нет подходящих меток</div>');
            }

            if (filter && !containsTag(filter)) {
                var exists = false;
                $.each(knownTags || [], function(_, tag) {
                    if (tag.toLowerCase() === filter) {
                        exists = true;
                        return false;
                    }
                });

                if (!exists) {
                    var newTag = normalizeTag($input.val());
                    var $add = $('<button type="button" class="tag-picker-add"></button>');
                    $add.text('Добавить "' + newTag + '"');
                    $add.on('click', function() {
                        addTag(newTag);
                    });
                    $menu.append($add);
                }
            }

            positionMenu();
        }

        function positionMenu() {
            if (!$picker.hasClass('is-open')) {
                return;
            }

            var offset = $control.offset();
            var controlHeight = $control.outerHeight();
            var menuHeight = Math.min($menu.outerHeight(), 240);
            var viewportTop = $(window).scrollTop();
            var viewportBottom = viewportTop + $(window).height();
            var belowTop = offset.top + controlHeight + 4;
            var aboveTop = offset.top - menuHeight - 4;
            var top = belowTop;

            if (belowTop + menuHeight > viewportBottom && aboveTop > viewportTop) {
                top = aboveTop;
            }

            $menu.css({
                top: top,
                left: offset.left,
                width: $control.outerWidth()
            });
        }

        function openMenu() {
            $picker.addClass('is-open');
            $menu.addClass('is-open').show();
            renderMenu();
            positionMenu();
        }

        function closeMenu() {
            $picker.removeClass('is-open');
            $menu.removeClass('is-open').hide();
        }

        $input.on('focus input', function() {
            openMenu();
        });

        $input.on('keydown', function(event) {
            if (event.key === 'Enter' || event.key === ',') {
                event.preventDefault();
                addTag($input.val());
            } else if (event.key === 'Backspace' && !$input.val() && tags.length) {
                removeTag(tags[tags.length - 1]);
            } else if (event.key === 'Escape') {
                closeMenu();
            }
        });

        $toggle.on('click', function() {
            if ($picker.hasClass('is-open')) {
                closeMenu();
            } else {
                $input.focus();
                openMenu();
            }
        });

        $picker.closest('form').on('submit', function() {
            if ($input.val()) {
                addTag($input.val());
            }
            writeTags($source, tags);
        });

        $(document).on('mousedown' + eventNamespace, function(event) {
            var insidePicker = $picker.is(event.target) || $.contains($picker[0], event.target);
            var insideMenu = $menu.is(event.target) || $.contains($menu[0], event.target);

            if (!insidePicker && !insideMenu) {
                closeMenu();
            }
        });

        $(window).on('resize' + eventNamespace + ' scroll' + eventNamespace, positionMenu);
        $picker.parents().filter(function() {
            var overflow = $(this).css('overflow') + $(this).css('overflow-y') + $(this).css('overflow-x');
            return /(auto|scroll)/.test(overflow);
        }).on('scroll' + eventNamespace, positionMenu);

        loadKnownTags(function(loadedTags) {
            knownTags = uniqueTags(loadedTags.concat(tags));
            setTags(tags, { silent: true });
        });

        writeTags($source, tags);
        renderSelected();
    }

    $('.tagsinput').each(function() {
        initTagPicker(this);
    });


    $(document).on('click', '.js-delete, .glyphicon-trash[data-uri]', function(event) {
        if (event.inventoryDeleteHandled) {
            return false;
        }

        event.inventoryDeleteHandled = true;
        event.preventDefault();
        event.stopImmediatePropagation();

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
