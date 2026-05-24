"""
routes/chat_routes.py - Workspace Messaging Blueprint
======================================================
Handles peer-to-peer workspace chats between employees and managers.
Uses AJAX polling for robust, Render-compatible real-time performance.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, User, Employee, Message

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/chat')
@login_required
def index():
    """Render the central chat workspace. Lists all admins and employees with unread counts."""
    # Fetch all users except current_user
    all_users = User.query.filter(User.user_id != current_user.user_id).all()
    
    admins = []
    employees = []
    
    for u in all_users:
        # Calculate unread count from this specific sender to the current logged-in user
        unread_count = Message.query.filter_by(
            sender_id=u.user_id,
            recipient_id=current_user.user_id,
            is_read=False
        ).count()
        
        # Structure contact object
        display_name = u.employee.full_name if (u.employee and u.employee.full_name) else u.username.capitalize()
        dept = u.employee.department if u.employee else 'Administration'
        initial = display_name[0].upper()
        
        contact = {
            'user_id': u.user_id,
            'username': u.username,
            'display_name': display_name,
            'department': dept,
            'initial': initial,
            'role': u.role,
            'unread_count': unread_count
        }
        
        if u.role == 'admin':
            admins.append(contact)
        else:
            employees.append(contact)

    return render_template('chat.html', admins=admins, employees=employees, title='Chat Workspace')


@chat_bp.route('/chat/history/<int:partner_id>')
@login_required
def history(partner_id):
    """Retrieve chat history between current user and the selected contact. Marks received messages as read."""
    # Verify contact exists
    partner = User.query.get_or_404(partner_id)
    
    # Query conversation
    messages = Message.query.filter(
        ((Message.sender_id == current_user.user_id) & (Message.recipient_id == partner_id)) |
        ((Message.sender_id == partner_id) & (Message.recipient_id == current_user.user_id))
    ).order_by(Message.timestamp.asc()).all()
    
    # Mark messages received by current user as Read
    unread_messages = [m for m in messages if m.recipient_id == current_user.user_id and not m.is_read]
    if unread_messages:
        for m in unread_messages:
            m.is_read = True
        db.session.commit()
        
    # Serialize message records
    serialized = []
    for m in messages:
        serialized.append({
            'message_id': m.message_id,
            'sender_id': m.sender_id,
            'content': m.content,
            'timestamp': m.timestamp.strftime('%I:%M %p'),
            'date': m.timestamp.strftime('%d %b %Y')
        })
        
    return jsonify({
        'status': 'success',
        'messages': serialized,
        'partner': {
            'user_id': partner.user_id,
            'display_name': partner.employee.full_name if (partner.employee and partner.employee.full_name) else partner.username.capitalize(),
            'role': partner.role.capitalize(),
            'department': partner.employee.department if partner.employee else 'Administration'
        }
    })


@chat_bp.route('/chat/send', methods=['POST'])
@login_required
def send():
    """Secure API endpoint to save a new text message. Expects JSON body with recipient_id and content."""
    data = request.get_json() or {}
    recipient_id = data.get('recipient_id')
    content = data.get('content', '').strip()
    
    if not recipient_id or not content:
        return jsonify({'status': 'error', 'message': 'Missing recipient or message content.'}), 400
        
    # Verify recipient exists
    recipient = User.query.get(recipient_id)
    if not recipient:
        return jsonify({'status': 'error', 'message': 'Recipient user not found.'}), 404
        
    # Insert new message
    new_message = Message(
        sender_id=current_user.user_id,
        recipient_id=recipient_id,
        content=content
    )
    db.session.add(new_message)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': {
            'message_id': new_message.message_id,
            'sender_id': new_message.sender_id,
            'content': new_message.content,
            'timestamp': new_message.timestamp.strftime('%I:%M %p')
        }
    })
