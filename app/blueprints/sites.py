from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from ..models.core import Site
from flask_login import login_required


bp = Blueprint('sites', __name__)

@bp.route('/')
@login_required
def list_sites():
    sites = Site.query.order_by(Site.name).all()
    return render_template('sites/list.html', sites=sites)

@bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_site():
    if request.method == 'POST':
        name = request.form.get('name')
        capacity_kwp = request.form.get('capacity_kwp', type=float)
        location = request.form.get('location')
        if not name or capacity_kwp is None:
            flash('Name and capacity required', 'error')
            return redirect(url_for('sites.new_site'))
        s = Site(name=name, capacity_kwp=capacity_kwp, location=location)
        db.session.add(s)
        db.session.commit()
        flash('Site created', 'success')
        return redirect(url_for('sites.list_sites'))
    return render_template('sites/form.html', site=None)

@bp.route('/<int:site_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_site(site_id):
    s = Site.query.get_or_404(site_id)
    if request.method == 'POST':
        s.name = request.form.get('name')
        s.capacity_kwp = request.form.get('capacity_kwp', type=float)
        s.location = request.form.get('location')
        db.session.commit()
        flash('Site updated', 'success')
        return redirect(url_for('sites.list_sites'))
    return render_template('sites/form.html', site=s)

@bp.route('/<int:site_id>/delete', methods=['POST'])
@login_required
def delete_site(site_id):
    s = Site.query.get_or_404(site_id)
    db.session.delete(s)
    db.session.commit()
    flash('Site deleted', 'success')
    return redirect(url_for('sites.list_sites'))