/*jslint browser: true, forin: true, eqeq: true, white: true, sloppy: true, vars: true, nomen: true */
/*global $, jQuery, _, asm, common, config, controller, dlgfx, format, header, html, tableform, validate */

$(function() {

    var onlineforms = {

        model: function() {
            var dialog = {
                add_title: _("Add online form"),
                edit_title: _("Edit online form"),
                edit_perm: 'eof',
                helper_text: _("Forms need a name."),
                close_on_ok: false,
                columns: 1,
                width: 850,
                fields: [
                    { json_field: "NAME", post_field: "name", label: _("Name"), type: "text", validation: "notblank" },
                    { json_field: "REDIRECTURLAFTERPOST", post_field: "redirect", label: _("Redirect to URL after POST"), 
                        type: "text", classes: "asm-doubletextbox", 
                        tooltip: _("After the user presses submit and ASM has accepted the form, redirect the user to this URL"),
                        callout: _("After the user presses submit and ASM has accepted the form, redirect the user to this URL") },
                    { json_field: "SETOWNERFLAGS", post_field: "flags", label: _("Person Flags"), type: "selectmulti" },
                    { json_field: "EMAILADDRESS", post_field: "email", label: _("Email submissions to"), type: "textarea", rows: "2", 
                        validation: "validemail", 
                        tooltip: _("Email incoming form submissions to this comma separated list of email addresses"), 
                        callout: _("Email incoming form submissions to this comma separated list of email addresses") }, 
                    { json_field: "EMAILSUBMITTER", post_field: "emailsubmitter", label: _("Send confirmation email to form submitter"), type: "check",
                        tooltip: _("If this form has a populated emailaddress field during submission, send a confirmation email to it"),
                        callout: _("If this form has a populated emailaddress field during submission, send a confirmation email to it") },
                    { json_field: "EMAILMESSAGE", post_field: "emailmessage", label: _("Confirmation message"), type: "richtextarea", 
                        margintop: "0px", height: "100px", width: "600px",
                        tooltip: _("The confirmation email message to send to the form submitter. Leave blank to send a copy of the completed form."),
                        callout: _("The confirmation email message to send to the form submitter. Leave blank to send a copy of the completed form.") }, 
                    { json_field: "DESCRIPTION", post_field: "description", label: _("Description"), type: "htmleditor", height: "100px", width: "600px" },
                    { json_field: "HEADER", post_field: "header", label: _("Header"), type: "htmleditor", height: "100px", width: "600px" },
                    { json_field: "FOOTER", post_field: "footer", label: _("Footer"), type: "htmleditor", height: "100px", width: "600px" }
                ]
            };

            var table = {
                rows: controller.rows,
                idcolumn: "ID",
                edit: function(row) {
                    tableform.dialog_show_edit(dialog, row)
                        .then(function() {
                            onlineforms.check_redirect_url();
                            tableform.fields_update_row(dialog.fields, row);
                            return tableform.fields_post(dialog.fields, "mode=update&formid=" + row.ID, "onlineforms");
                        })
                        .then(function(response) {
                            tableform.table_update(table);
                            tableform.dialog_close();
                        })
                        .fail(function() {
                            tableform.dialog_enable_buttons();
                        });
                },
                columns: [
                    { field: "NAME", display: _("Name"), initialsort: true, formatter: function(row) {
                        return "<span style=\"white-space: nowrap\">" + 
                            "<input type=\"checkbox\" data-id=\"" + row.ID + "\" title=\"" + html.title(_("Select")) + "\" />" +
                            "<a href=\"onlineform?formid=" + row.ID + "\">" + row.NAME + "</a>" +
                            "<a href=\"#\" class=\"link-edit\" data-id=\"" + row.ID + "\">" + html.icon("edit", _("Edit online form")) + "</a>" +
                            "</span>";
                    }},
                    { field: "", display: _("Form URL"), formatter: function(row) {
                            var u = "?";
                            if (asm.useraccountalias) { u += "account=" + asm.useraccountalias + "&"; }
                            u += "method=online_form_html&formid=" + row.ID;
                            return '<a target="_blank" href="' + asm.serviceurl + u + '">' + u + '</a>';
                        }},
                    { field: "REDIRECTURLAFTERPOST", display: _("Redirect to URL after POST") },
                    { field: "EMAILADDRESS", display: _("Email submissions to") },
                    { field: "SETOWNERFLAGS", display: _("Person Flags"), formatter: function(row) { return row.SETOWNERFLAGS.split("|").join(", "); }},
                    { field: "NUMBEROFFIELDS", display: _("Number of fields") },
                    { field: "DESCRIPTION", display: _("Description"), formatter: function(row) { return html.truncate(row.DESCRIPTION); } }
                ]
            };

            var buttons = [
                 { id: "new", text: _("New online form"), icon: "new", enabled: "always", 
                     click: function() { 
                         tableform.dialog_show_add(dialog)
                             .then(function() {
                                 onlineforms.check_redirect_url();
                                 return tableform.fields_post(dialog.fields, "mode=create", "onlineforms");
                             })
                             .then(function(response) {
                                 var row = {};
                                 row.ID = response;
                                 tableform.fields_update_row(dialog.fields, row);
                                 controller.rows.push(row);
                                 tableform.table_update(table);
                                 tableform.dialog_close();
                            })
                            .fail(function() {
                                 tableform.dialog_enable_buttons();
                            });
                     } 
                 },
                 { id: "clone", text: _("Clone"), icon: "copy", enabled: "multi", 
                     click: function() { 
                         tableform.buttons_default_state(buttons);
                         var ids = tableform.table_ids(table);
                         common.ajax_post("onlineforms", "mode=clone&ids=" + ids)
                             .then(function() {
                                 common.route_reload();
                             });
                     } 
                 },
                 { id: "delete", text: _("Delete"), icon: "delete", enabled: "multi", 
                     click: function() { 
                         tableform.delete_dialog()
                             .then(function() {
                                 tableform.buttons_default_state(buttons);
                                 var ids = tableform.table_ids(table);
                                 return common.ajax_post("onlineforms", "mode=delete&ids=" + ids);
                             })
                             .then(function() {
                                 tableform.table_remove_selected_from_json(table, controller.rows);
                                 tableform.table_update(table);
                             });
                     } 
                 },
                 { id: "headfoot", text: _("Edit Header/Footer"), icon: "forms", enabled: "always", tooltip: _("Edit online form HTML header/footer"),
                     click: function() {
                        $("#dialog-headfoot").dialog("open");
                     }
                 },
                 { id: "import", text: _("Import"), icon: "database", enabled: "always", tooltip: _("Import from file"),
                     click: function() {
                         tableform.show_okcancel_dialog("#dialog-import", _("Import"), { notblank: ["filechooser"] })
                             .then(function() {
                                 $("#importform").submit();
                             });
                     }
                 }
            ];
            this.dialog = dialog;
            this.table = table;
            this.buttons = buttons;
        },

        load_person_flags: function() {
            var field_option = function(post, label) {
                return '<option value="' + post + '">' + label + '</option>\n';
            };
            var flag_option = function(flag) {
                return '<option value="' + html.title(flag) + '">' + flag + '</option>';
            };
            var h = [
                field_option("aco", _("ACO")),
                field_option("banned", _("Banned")),
                field_option("donor", _("Donor")),
                field_option("driver", _("Driver")),
                field_option("fosterer", _("Fosterer")),
                field_option("homechecked", _("Homechecked")),
                field_option("homechecker", _("Homechecker")),
                field_option("member", _("Member")),
                field_option("shelter", _("Other Shelter")),
                field_option("retailer", _("Retailer")),
                field_option("staff", _("Staff")),
                asm.locale == "en_GB" ? field_option("giftaid", _("UK Giftaid")) : "",
                field_option("vet", _("Vet")),
                field_option("volunteer", _("Volunteer"))
            ];
            $.each(controller.flags, function(i, v) {
                h.push(flag_option(v.FLAG));
            });
            $("#flags").html(h.join("\n"));
            $("#flags").change();
        },

        render_headfoot: function() {
            return [
                '<div id="dialog-headfoot" style="display: none" title="' + html.title(_("Edit Header/Footer")) + '">',
                '<div class="ui-state-highlight ui-corner-all">',
                    '<p>',
                        '<span class="ui-icon ui-icon-info" style="float: left; margin-right: .3em;"></span>',
                        _("These are the HTML headers and footers used when displaying online forms."),
                    '</p>',
                '</div>',
                '<table width="100%">',
                '<tr>',
                '<td valign="top">',
                '<label for="rhead">' + _("Header") + '</label><br />',
                '<textarea id="rhead" data="header" class="asm-htmleditor headfoot" data-height="250px" data-width="750px">',
                controller.header,
                '</textarea>',
                '<label for="rfoot">' + _("Footer") + '</label><br />',
                '<textarea id="rfoot" data="footer" class="asm-htmleditor headfoot" data-height="250px" data-width="750px">',
                controller.footer,
                '</textarea>',
                '</td>',
                '</tr>',
                '</table>',
                '</div>'
            ].join("\n");
        },

        render_import: function() {
            return [
                '<div id="dialog-import" style="display: none" title="' + html.title(_("Import from file")) + '">',
                '<form id="importform" action="onlineforms" method="post" enctype="multipart/form-data">',
                '<input name="mode" value="import" type="hidden" />',
                '<input id="filechooser" name="filechooser" type="file" />',
                '</form>',
                '</div>'
            ].join("\n");
        },

        bind_headfoot: function() {
            var headfootbuttons = {};
            headfootbuttons[_("Save")] = function() {
                var formdata = "mode=headfoot&" + $(".headfoot").toPOST();
                common.ajax_post("onlineforms", formdata)
                    .then(function() { 
                        header.show_info(_("Updated."));
                    })
                    .always(function() {
                        $("#dialog-headfoot").dialog("close");
                    });
            };
            headfootbuttons[_("Cancel")] = function() { $(this).dialog("close"); };
            $("#dialog-headfoot").dialog({
                autoOpen: false,
                resizable: true,
                height: "auto",
                width: 800,
                modal: true,
                dialogClass: "dialogshadow",
                show: dlgfx.add_show,
                hide: dlgfx.add_hide,
                buttons: headfootbuttons,
                open: function() {
                    $("#rhead, #rfoot").htmleditor("refresh");
                }
            });
        },

        check_redirect_url: function() {
            var u = $("#redirect").val();
            if (u && u.indexOf("http") != 0) { $("#redirect").val( "https://" + u ); }
        },

        render: function() {
            var s = "";
            this.model();
            s += this.render_headfoot();
            s += this.render_import();
            s += tableform.dialog_render(this.dialog);
            s += html.content_header(_("Online Forms"));
            s += html.info(_("Online forms can be linked to from your website and used to take information from visitors for applications, etc."));
            s += tableform.buttons_render(this.buttons);
            s += tableform.table_render(this.table);
            s += html.content_footer();
            return s;
        },

        bind: function() {
            tableform.dialog_bind(this.dialog);
            tableform.buttons_bind(this.buttons);
            tableform.table_bind(this.table, this.buttons);
            this.bind_headfoot();
            this.load_person_flags();
        },

        destroy: function() {
            common.widget_destroy("#dialog-headfoot");
            common.widget_destroy("#dialog-import");
            common.widget_destroy("#rhead");
            common.widget_destroy("#rfoot");
            tableform.dialog_destroy();
        },

        name: "onlineforms",
        animation: "formtab",
        title: function() { return _("Online Forms"); },
        routes: { 
            "onlineforms": function() { common.module_loadandstart("onlineforms", "onlineforms"); }
        }

    };
    
    common.module_register(onlineforms);

});
