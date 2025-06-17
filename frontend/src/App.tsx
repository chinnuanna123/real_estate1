import React, { useEffect, useRef, useState } from 'react';
import './App.css';
import { v4 as uuidv4 } from 'uuid';

interface ChatMessage {
  id: string;
  sender: 'user' | 'bot';
  content: string;
  propertyDetails?: PropertyDetails[];
}

interface PropertyDetails {
  id: string;
  name: string;
  location: string;
  price: string;
  bedrooms: number;
  bathrooms: number;
  areaSqFt: number;
  description: string;
  imageUrl: string;
  link?: string;
}

interface SelectedProperty extends PropertyDetails {
  selected_at: string;
  selection_id: string;
  status: 'interested' | 'shortlisted' | 'visited' | 'rejected' | 'purchased';
  user_notes: string;
}

interface SelectionSummary {
  total_selected: number;
  preferred_locations: string[];
  price_range: string[];
  bedroom_preferences: number[];
  selection_pattern: string;
}

const API_BASE_URL = "http://127.0.0.1:8000/api/v1/home_buying";

const extractPriceFromText = (text: string): string | undefined => {
  const match = text.match(/(\d+\.?\d*)\s*(lakh|lakhs|crore|cr)/i);
  if (match) {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const [_, value, unit] = match;
    const normalized = unit.toLowerCase().includes("cr") ? `${value} Crore` : `${value} Lakh`;
    return `₹${normalized}`;
  }
  return undefined;
};

function App() {
  const [userId, setUserId] = useState<string>('');
  const [userQuery, setUserQuery] = useState('');
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedProperty, setSelectedProperty] = useState<PropertyDetails | null>(null);
  
  // New state for AI memory features
  const [selectedProperties, setSelectedProperties] = useState<SelectedProperty[]>([]);
  const [selectionSummary, setSelectionSummary] = useState<SelectionSummary | null>(null);
  const [showSelectedPanel, setShowSelectedPanel] = useState(false);
  const [insights, setInsights] = useState<string>('');
  const [selectedPropertyIds, setSelectedPropertyIds] = useState<Set<string>>(new Set());

  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const storedUserId = localStorage.getItem('ai_home_buyer_user_id') || uuidv4();
    localStorage.setItem('ai_home_buyer_user_id', storedUserId);
    setUserId(storedUserId);
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chat]);

  // Load user's selected properties
  const loadSelectedProperties = React.useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/selected_properties/${userId}`);
      const result = await response.json();

      if (result.status === 'success') {
        setSelectedProperties(result.data.selected_properties);
        setSelectionSummary(result.data.summary);
        
        // Update selected property IDs for UI state
        const ids = new Set<string>(result.data.selected_properties.map((p: SelectedProperty) => (p.link || p.id) as string));
        setSelectedPropertyIds(ids);
      }
    } catch (error) {
      console.error('Error loading selected properties:', error);
    }
  }, [userId]);

  // Load AI insights about user's selections
  const loadSelectionInsights = React.useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/selection_insights/${userId}`);
      const result = await response.json();

      if (result.status === 'success') {
        setInsights(result.data.insights);
      }
    } catch (error) {
      console.error('Error loading insights:', error);
    }
  }, [userId]);

  useEffect(() => {
    if (userId) {
      loadSelectedProperties();
      loadSelectionInsights();
    }
  }, [userId, loadSelectedProperties, loadSelectionInsights]);

  const appendBotMessage = (content: string, propertyDetails?: PropertyDetails[]) => {
    setChat(prev => [...prev, {
      id: uuidv4(),
      sender: 'bot',
      content,
      propertyDetails
    }]);
  };

  const handleSend = async () => {
    if (!userQuery.trim()) return;

    const newUserMessage: ChatMessage = {
      id: uuidv4(),
      sender: 'user',
      content: userQuery
    };
    setChat(prev => [...prev, newUserMessage]);
    setUserQuery('');
    setIsLoading(true);

    try {
      const targetPrice = extractPriceFromText(newUserMessage.content);

      console.log("Sending chat history to backend:", chat);
      const res = await fetch(`${API_BASE_URL}/process_query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId, // AI now has memory!
          query: newUserMessage.content,
          property_details: selectedProperty || undefined,
          target_negotiation_price: targetPrice || undefined,
          chat_history: chat.map(msg => ({
            role: msg.sender === 'user' ? 'user' : 'assistant',
            text: msg.content
          }))
        })
      });

      const result = await res.json();

      if (result.status === 'success' && result.data) {
        const type = result.data.type;
        let content = '';

        switch (type) {
          case 'properties':
            content = result.data.data.length > 0 
              ? 'Here are some property options based on your request:'
              : 'No properties found matching your criteria.';
            break;
          case 'comparison_result':
          case 'selection_insights':
          case 'negotiation_result':
          case 'legal_guidance':
          case 'mortgage_recommendation':
          case 'neighborhood_insights':
          case 'marketing_description':
            content = result.data.data;
            break;
          default:
            content = result.response || 'Sorry, I could not understand that.';
        }

        const propertyDetails = type === 'properties' ? result.data.data : undefined;
        appendBotMessage(content, propertyDetails);

        // Refresh selections if AI provided insights about them
        if (type === 'comparison_result' || type === 'selection_insights') {
          await loadSelectedProperties();
          await loadSelectionInsights();
        }
      } else {
        appendBotMessage(result.response || 'Sorry, something went wrong processing your request.');
      }
    } catch (err) {
      console.error(err);
      appendBotMessage('An error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Enhanced property selection with API call
  const handlePropertySelect = async (property: PropertyDetails) => {
    // Check if already selected
    if (selectedPropertyIds.has(property.link || property.id)) {
      appendBotMessage(`${property.name} is already in your selections!`);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/select_property`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          property_data: property
        })
      });

      const result = await response.json();

      if (result.status === 'success') {
        // Update local state
        setSelectedProperty(property);
        setSelectedPropertyIds(prev => {
          const newSet = new Set<string>(Array.from(prev));
          newSet.add(property.link || property.id);
          return newSet;
        });
        
        // Refresh selections and insights
        await loadSelectedProperties();
        await loadSelectionInsights();
        
        appendBotMessage(`✅ ${result.message} You now have ${(selectionSummary?.total_selected || 0) + 1} selected properties. Ask me to compare them or provide insights!`);
      } else {
        appendBotMessage(`⚠️ ${result.message || 'Failed to select property'}`);
      }
    } catch (error) {
      console.error('Error selecting property:', error);
      appendBotMessage('❌ Failed to select property. Please try again.');
    }
  };

  // Update property status
  const updatePropertyStatus = async (selectionId: string, newStatus: string, notes: string = '') => {
    try {
      const response = await fetch(`${API_BASE_URL}/update_property_status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          selection_id: selectionId,
          status: newStatus,
          notes: notes
        })
      });

      const result = await response.json();

      if (result.status === 'success') {
        await loadSelectedProperties();
        appendBotMessage(`✅ Property status updated to ${newStatus}`);
      }
    } catch (error) {
      console.error('Error updating status:', error);
    }
  };

  // Remove property from selections
  const removeSelectedProperty = async (selectionId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/remove_selected_property`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          selection_id: selectionId
        })
      });

      const result = await response.json();

      if (result.status === 'success') {
        await loadSelectedProperties();
        appendBotMessage(`✅ ${result.message}`);
      }
    } catch (error) {
      console.error('Error removing property:', error);
    }
  };

  // Quick actions for common queries
  const handleQuickAction = (action: string) => {
    let query = '';
    switch (action) {
      case 'compare':
        query = 'Compare my selected properties';
        break;
      case 'insights':
        query = 'What patterns do you see in my property selections?';
        break;
      case 'recommendations':
        query = 'Based on my selections, what should I look for next?';
        break;
      case 'budget':
        query = 'Analyze my budget based on selected properties';
        break;
    }
    setUserQuery(query);
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <h1 className="app-title">🏠 AI Home Buying Assistant</h1>
        <div className="header-actions">
          <button 
            onClick={() => setShowSelectedPanel(!showSelectedPanel)}
            className="toggle-panel-btn"
          >
            📋 My Selections ({selectedProperties.length})
          </button>
        </div>
      </header>

      <div className="main-content">
        {/* Chat Section */}
        <div className="chat-section">
          <div className="chat-container">
            <div className="chat-box">
              {chat.map(msg => (
                <div key={msg.id} className={`chat-message ${msg.sender}`}>
                  <p className="chat-content">{msg.content}</p>
                  {msg.propertyDetails && (
                    <div className="property-grid">
                      {msg.propertyDetails.map(p => {
                        const isSelected = selectedPropertyIds.has(p.link || p.id);
                        return (
                          <div key={p.id} className="property-card">
                            <img src={p.imageUrl} alt={p.name} className="property-image" />

                            <h3 className="text-lg font-bold underline">
                              {p.link ? (
                                <a href={p.link} target="_blank" rel="noopener noreferrer">{p.name}</a>
                              ) : p.name}
                            </h3>

                            <p className="text-sm text-gray-600">{p.location}</p>

                            <div className="text-sm font-medium my-1">
                              💰 <strong>{p.price}</strong> | 📐 {p.areaSqFt} sqft | 🛏 {p.bedrooms} BHK | 🛁 {p.bathrooms} Baths
                            </div>

                            <p className="text-sm text-gray-700">{p.description}</p>

                            {p.link && (
                              <a href={p.link} target="_blank" rel="noopener noreferrer" className="text-blue-600 text-sm mt-1 block">
                                View Source
                              </a>
                            )}

                            <button 
                              onClick={() => handlePropertySelect(p)} 
                              className={`select-button mt-2 ${isSelected ? 'selected' : ''}`}
                              disabled={isSelected}
                            >
                              {isSelected ? '✅ Selected' : 'Select This'}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>

            {/* Quick Actions */}
            {selectedProperties.length > 0 && (
              <div className="quick-actions">
                <h4>🚀 Quick Actions:</h4>
                <div className="action-buttons">
                  <button onClick={() => handleQuickAction('compare')} className="action-btn">
                    📊 Compare Properties
                  </button>
                  <button onClick={() => handleQuickAction('insights')} className="action-btn">
                    🎯 Get Insights
                  </button>
                  <button onClick={() => handleQuickAction('recommendations')} className="action-btn">
                    💡 Recommendations
                  </button>
                  <button onClick={() => handleQuickAction('budget')} className="action-btn">
                    💰 Budget Analysis
                  </button>
                </div>
              </div>
            )}

            <div className="input-box">
              <textarea
                placeholder={selectedProperties.length > 0 
                  ? "Ask me to compare your selections, get insights, or search for more properties..." 
                  : "Describe your ideal home..."}
                value={userQuery}
                onChange={(e) => setUserQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                disabled={isLoading}
              />
              <button onClick={handleSend} disabled={isLoading}>
                {isLoading ? '...' : 'Send'}
              </button>
            </div>
          </div>
        </div>

        {/* Selected Properties Panel */}
        {showSelectedPanel && (
          <div className="selected-panel">
            <div className="panel-header">
              <h2>📋 Your Selected Properties ({selectedProperties.length})</h2>
              <button onClick={() => setShowSelectedPanel(false)} className="close-btn">×</button>
            </div>

            {/* AI Insights */}
            {insights && (
              <div className="insights-section">
                <h3>🎯 AI Insights</h3>
                <div className="insights-content">
                  {insights}
                </div>
              </div>
            )}

            {/* Selection Summary */}
            {selectionSummary && selectionSummary.total_selected > 0 && (
              <div className="summary-section">
                <h4>📊 Quick Summary</h4>
                <div className="summary-stats">
                  <span>📍 Locations: {selectionSummary.preferred_locations.slice(0, 3).join(', ')}</span>
                  <span>💰 Price Range: {selectionSummary.price_range.slice(0, 3).join(', ')}</span>
                  <span>🛏 BHK: {selectionSummary.bedroom_preferences.join(', ')}</span>
                </div>
              </div>
            )}

            {/* Properties List */}
            <div className="selected-properties-list">
              {selectedProperties.length === 0 ? (
                <div className="empty-state">
                  <p>No properties selected yet.</p>
                  <p>Start exploring and click "Select This" on properties you like!</p>
                </div>
              ) : (
                selectedProperties.map((property) => (
                  <div key={property.selection_id} className="selected-property-card">
                    <div className="property-header">
                      <h4>{property.name}</h4>
                      <span className={`status-badge status-${property.status}`}>
                        {property.status}
                      </span>
                    </div>
                    
                    <p>📍 {property.location}</p>
                    <p>💰 {property.price}</p>
                    <p>📅 Selected: {new Date(property.selected_at).toLocaleDateString()}</p>
                    
                    <div className="property-actions">
                      <button 
                        onClick={() => updatePropertyStatus(property.selection_id, 'shortlisted')}
                        className="action-btn-small"
                      >
                        ⭐ Shortlist
                      </button>
                      <button 
                        onClick={() => updatePropertyStatus(property.selection_id, 'visited')}
                        className="action-btn-small"
                      >
                        👁️ Visited
                      </button>
                      <button 
                        onClick={() => updatePropertyStatus(property.selection_id, 'rejected')}
                        className="action-btn-small"
                      >
                        ❌ Reject
                      </button>
                      <button 
                        onClick={() => removeSelectedProperty(property.selection_id)}
                        className="action-btn-small remove-btn"
                      >
                        🗑️ Remove
                      </button>
                    </div>
                    
                    {property.link && (
                      <a href={property.link} target="_blank" rel="noopener noreferrer" className="view-property-link">
                        🔗 View Property
                      </a>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;