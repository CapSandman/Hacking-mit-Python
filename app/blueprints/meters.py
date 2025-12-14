from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from ..models.core import Meter, Site
from flask_login import login_required


bp = Blueprint('meters', __name__)

@bp.route('/')
@login_required
def list_meters():
    meters = db.session.query(Meter, Site).join(Site, Meter.site_id == Site.id)
    return render_template('meters/list.html', meters=meters)

@bp.route('/new', methods=['GET','POST'])
@login_required
def new_meter():
    sites = Site.query.order_by(Site.name).all()
    if request.method == 'POST':
        site_id = request.form.get('site_id', type=int)
        name = request.form.get('name')
        m = Meter(site_id=site_id, name=name)
        db.session.add(m)
        db.session.commit()
        flash('Meter created', 'success')
        return redirect(url_for('meters.list_meters'))
    return render_template('meters/form.html', meter=None, sites=sites)

@bp.route('/<int:meter_id>/edit', methods=['GET','POST'])
@login_required
def edit_meter(meter_id):
    m = Meter.query.get_or_404(meter_id)
    sites = Site.query.order_by(Site.name).all()
    if request.methods == 'POST':
        m.site_id = request.form.get('site_id', type=int)
        m.name = request.form.get('name')
        db.session.commit()
        flash('Meter updated', 'success')
        return redirect(url_for('meters.list_meters'))
    return render_template('meters/form.html', meter=m, sites=sites)

@bp.route('/<int:meter_id>/delete', methods=['POST'])
@login_required
def delete_meter(meter_id):
    m = Meter.query.get_or_404(meter_id)
    db.session.delete(m)
    db.session.commit()
    flash('Meter deleted', 'success')
    return redirect(url_for('meters.list_meters'))