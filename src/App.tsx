import React, { useState, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid'; // Import uuid

// Define the type for Google Search Results (raw from tool)
interface GoogleSearchResult {
  title: string;
  snippet: string;
  link: string;
}

// Define interfaces for data structures based on your backend
interface PropertyDetails {
  id: string;
  name: string;
  location: string;
  price: string; // Keep as string as LLM returns this way (e.g., "₹1.5 Crore")
  bedrooms: number;
  bathrooms: number;
  areaSqFt: number;
  description: string;
  imageUrl: string;
  link?: string; // Optional for Google Search results
}

interface ProcessQueryRequest {
  user_id: string;
  query: string;
  property_details?: PropertyDetails;
  target_negotiation_price?: string;
  // Parameters for mortgage recommendation, directly passed to backend
  income?: number;
  credit_score?: number;
  down_payment?: number;
  loan_amount?: number;
  property_type?: string;
}

// Define the expected successful API response structure for /process_query endpoint
interface ProcessQueryResponseSuccess {
  status: 'success';
  data:
    | { type: 'properties'; data: PropertyDetails[] }
    | { type: 'Google Search'; data: GoogleSearchResult[] }
    | { type: 'negotiation_result'; data: string }
    | { type: 'legal_guidance'; data: string }
    | { type: 'mortgage_recommendation'; data: string } // Ensure this matches backend exactly
    | { type: 'neighborhood_insights'; data: string }
    | { type: 'marketing_description'; data: string }
    | { type: 'error'; message: string; error?: string; }; // Explicitly define error structure within 'data'
}

// Define the expected successful API response structure for /load_preferences and /save_preferences
interface LoadSavePreferencesResponseSuccess {
  status: 'success';
  data?: { // Data is optional for save_preferences, but present for load_preferences
    homePreferences?: string;
    lastSearchResults?: PropertyDetails[];
  };
  message?: string; // For save_preferences success message
}

// Define the expected error API response structure from FastAPI HTTPException
interface ApiResponseError {
  detail: string;
}

// Ensure Tailwind CSS is available in the environment.
// This code assumes Tailwind CSS is configured and available.

// Define your FastAPI backend URL
const API_BASE_URL = "http://127.0.0.1:8000/api/v1/home_buying"; // Corrected to match your router prefix

function App() {
  const [userId, setUserId] = useState<string | null>(null);
  const [isAppReady, setIsAppReady] = useState(false);
  const [userQuery, setUserQuery] = useState<string>(''); // Changed from 'preferences' for clarity
  const [properties, setProperties] = useState<PropertyDetails[]>([]); // Can hold both mock & parsed Google
  const [googleSearchResultsRaw, setGoogleSearchResultsRaw] = useState<GoogleSearchResult[]>([]); // For raw Google results display
  const [isLoading, setIsLoading] = useState(false);
  const [selectedProperty, setSelectedProperty] = useState<PropertyDetails | null>(null);
  const [message, setMessage] = useState<{ text: string; type: string } | null>(null); // Use null for no message

  // Modals and their data
  const [negotiationResult, setNegotiationResult] = useState<string>('');
  const [showNegotiationModal, setShowNegotiationModal] = useState<boolean>(false);
  const [legalGuidance, setLegalGuidance] = useState<string>('');
  const [showLegalModal, setShowLegalModal] = useState<boolean>(false);
  const [mortgageRecommendations, setMortgageRecommendations] = useState<string>(''); // Changed to string as LLM gives text
  const [showMortgageModal, setShowMortgageModal] = useState<boolean>(false);
  const [neighborhoodInsights, setNeighborhoodInsights] = useState<string>('');
  const [showNeighborhoodModal, setShowNeighborhoodModal] = useState<boolean>(false);
  const [marketingDescription, setMarketingDescription] = useState<string>('');
  const [showMarketingDescriptionModal, setShowMarketingDescriptionModal] = useState<boolean>(false);

  // Input for negotiation
  const [targetNegotiationPrice, setTargetNegotiationPrice] = useState<string>('');

  // Inputs for mortgage - sensible defaults for India
  const [mortgageIncome, setMortgageIncome] = useState<number>(1200000); // Example: 12 Lakhs annual
  const [mortgageCreditScore, setMortgageCreditScore] = useState<number>(750);
  const [mortgageDownPayment, setMortgageDownPayment] = useState<number>(2000000); // Example: 20 Lakhs
  const [mortgageLoanAmount, setMortgageLoanAmount] = useState<number>(8000000); // Example: 80 Lakhs
  const [mortgagePropertyType, setMortgagePropertyType] = useState<string>('apartment');


  // Initialize unique user ID from localStorage or generate a new one
  useEffect(() => {
    const currentUserId: string = localStorage.getItem('ai_home_buyer_user_id') || uuidv4();
    localStorage.setItem('ai_home_buyer_user_id', currentUserId);

    setUserId(currentUserId);
    console.log('User ID set:', currentUserId);
    setIsAppReady(true); // App is ready once user ID is determined
  }, []);

  // Load user preferences from backend when app is ready and userId is available
  useEffect(() => {
    const loadUserPreferencesFromBackend = async () => {
      if (isAppReady && userId) {
        try {
          const response = await fetch(`${API_BASE_URL}/load_preferences/${userId}`);
          
          if (!response.ok) {
            // If response is not OK, it's an HTTP error (e.g., 404 Not Found)
            const errorResult: ApiResponseError = await response.json();
            // Only set error message if it's not a "Not Found" for initial load
            if (response.status === 404) {
                setMessage({ text: 'No previous preferences found for this user.', type: 'info' });
            } else {
                // For other HTTP errors, still treat as a critical error
                throw new Error(errorResult.detail || 'Failed to load preferences due to backend error.');
            }
            // Clear any existing preferences if loading failed
            setUserQuery('');
            setProperties([]);
            return; // Exit early if loading failed or not found
          }

          // If response is OK, it should be a success response
          const result: LoadSavePreferencesResponseSuccess = await response.json();

          if (result.status === 'success' && result.data) { // Check for result.data existence
            setUserQuery(result.data.homePreferences || '');
            setProperties(result.data.lastSearchResults || []); // Load last search results
            setMessage({ text: 'Preferences loaded successfully!', type: 'success' });
          } else {
            // This else block would hit if response.ok is true but status is not 'success'
            // or if data is unexpectedly empty.
            console.log("Unexpected success response structure for preferences load:", result);
            setMessage({ text: 'No previous preferences found or unexpected data format. Please save your preferences.', type: 'info' });
            setUserQuery('');
            setProperties([]);
          }
        } catch (error: any) {
          console.error("Error fetching user preferences from backend:", error);
          setMessage({ text: `Error loading preferences: ${error.message}`, type: 'error' });
          setUserQuery('');
          setProperties([]);
        }
      }
    };

    loadUserPreferencesFromBackend();
  }, [isAppReady, userId]); // Re-run when app readiness or userId changes

  // Function to save user preferences and results to backend
  const savePreferences = async (currentQuery: string, currentResults: PropertyDetails[]) => {
    if (!userId) {
      setMessage({ text: 'User not ready. Cannot save preferences.', type: 'error' });
      return;
    }
    try {
      // Assuming a /save_preferences endpoint exists in your backend
      const response = await fetch(`${API_BASE_URL}/save_preferences`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, preferences: { homePreferences: currentQuery, lastSearchResults: currentResults } })
      });

      if (response.ok) {
        // Use the specific interface for saving preferences
        const result: LoadSavePreferencesResponseSuccess = await response.json();
        setMessage({ text: result.message || 'Preferences saved successfully!', type: 'success' });
      } else {
        const errorResult: ApiResponseError = await response.json();
        setMessage({ text: `Failed to save preferences: ${errorResult.detail || 'Unknown error'}`, type: 'error' });
      }

    } catch (error: any) {
      console.error("Error saving preferences to backend:", error);
      setMessage({ text: `Error saving preferences: ${error.message}`, type: 'error' });
    }
  };

  // Centralized function to process all user queries
  const processAgentRequest = async (intentQuery: string, additionalParams: any = {}) => {
    if (!userId) {
      setMessage({ text: 'User ID not ready. Please try again.', type: 'error' });
      return;
    }

    setIsLoading(true);
    setMessage(null); // Clear previous messages
    setProperties([]); // Clear properties on new search
    setGoogleSearchResultsRaw([]); // Clear raw Google results on new search
    // Close all modals when a new request is made
    setShowNegotiationModal(false);
    setShowLegalModal(false);
    setShowMortgageModal(false);
    setShowNeighborhoodModal(false);
    setShowMarketingDescriptionModal(false);


    try {
      const response = await fetch(`${API_BASE_URL}/process_query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          query: intentQuery,
          ...additionalParams,
        })
      });

      // Handle non-OK responses (HTTP errors) first
      if (!response.ok) {
        const errorResult: ApiResponseError = await response.json(); // Expecting { "detail": "..." }
        throw new Error(errorResult.detail || 'Unknown backend error');
      }

      // If response is OK, parse it as ProcessQueryResponseSuccess
      const result: ProcessQueryResponseSuccess = await response.json();
      console.log('Backend Response:', result);

      if (result.status === 'success' && result.data) {
        switch (result.data.type) {
          case 'properties':
            setProperties(result.data.data);
            await savePreferences(userQuery, result.data.data); // Save the results
            setMessage({ text: 'Properties found!', type: 'success' });
            break;
          case 'Google Search': // Note the space in 'Google Search' from your backend tool
            // When PropertySearch falls back to Google Search, it returns raw google results.
            setGoogleSearchResultsRaw(result.data.data);
            setMessage({ text: 'No mocked properties found. Displaying raw Google Search results.', type: 'info' });
            break;
          case 'negotiation_result':
            setNegotiationResult(result.data.data);
            setShowNegotiationModal(true);
            setMessage({ text: 'Negotiation simulation complete!', type: 'success' });
            break;
          case 'legal_guidance':
            setLegalGuidance(result.data.data);
            setShowLegalModal(true);
            setMessage({ text: 'Legal guidance provided!', type: 'success' });
            break;
          case 'mortgage_recommendation': // Corrected to match backend module name precisely
            setMortgageRecommendations(result.data.data); // result.data.data is string
            setShowMortgageModal(true);
            setMessage({ text: 'Mortgage recommendations generated!', type: 'success' });
            break;
          case 'neighborhood_insights':
            setNeighborhoodInsights(result.data.data);
            setShowNeighborhoodModal(true);
            setMessage({ text: 'Neighborhood insights retrieved!', type: 'success' });
            break;
          case 'marketing_description':
            setMarketingDescription(result.data.data);
            setShowMarketingDescriptionModal(true);
            setMessage({ text: 'Marketing description generated!', type: 'success' });
            break;
          case 'error': // Explicitly handle backend errors wrapped in a 'success' status
            setMessage({ text: `Backend Error: ${result.data.message || 'Unknown error'}`, type: 'error' });
            break;
          default:
            // This assertion tells TypeScript that result.data at this point must have a 'type' property.
            // This is a pragmatic fix for TypeScript's sometimes over-aggressive type narrowing.
            setMessage({ text: `Received unknown response type: ${(result.data as { type: string }).type}`, type: 'warning' });
            break;
        }
      } else {
        // This 'else' block will be reached if `response.ok` was true, but `result.status` is not 'success'.
        // This implies a successful API call but a logical failure indicated by the backend's 'status' field.
        // Based on your backend, this block should ideally not be hit for /process_query.
        setMessage({ text: `Backend operation failed with unexpected status: ${result.status || 'Unknown'}`, type: 'error' });
      }

    } catch (error: any) {
      console.error("Error processing agent request:", error);
      setMessage({ text: `Client error: ${error.message}. Please ensure backend is running.`, type: 'error' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearchClick = () => {
    if (!userQuery.trim()) {
      setMessage({ text: 'Please describe your desired home to search.', type: 'info' });
      return;
    }
    processAgentRequest(userQuery); // User query directly goes to process_query
  };

  const handleNegotiateClick = () => {
    if (!selectedProperty) {
      setMessage({ text: 'Please select a property first to negotiate.', type: 'info' });
      return;
    }
    if (!targetNegotiationPrice.trim()) {
      setMessage({ text: 'Please enter a target price for negotiation.', type: 'info' });
      return;
    }
    processAgentRequest(`Simulate negotiation for ${selectedProperty.name}`, {
      property_details: selectedProperty,
      target_negotiation_price: targetNegotiationPrice
    });
  };

  const handleLegalGuidanceClick = () => {
    // Send the exact intent keyword
    processAgentRequest("LEGAL_GUIDANCE");
  };

  const handleMortgageRecommendationsClick = () => {
    // Basic validation for mortgage inputs
    if (mortgageIncome <= 0 || mortgageCreditScore <= 0 || mortgageDownPayment < 0 || mortgageLoanAmount <= 0) {
        setMessage({ text: 'Please enter valid positive numbers for all mortgage inputs.', type: 'info' });
        return;
    }
    if (mortgageDownPayment + mortgageLoanAmount <= 0) {
        setMessage({ text: 'Down payment and loan amount cannot both be zero.', type: 'info' });
        return;
    }

    // Robust price parsing from selectedProperty.price string
    let effectiveLoanAmount = mortgageLoanAmount;
    let effectiveDownPayment = mortgageDownPayment;
    let effectivePropertyType = mortgagePropertyType;

    if (selectedProperty) {
        const priceString = selectedProperty.price.replace(/[₹,]/g, '').toLowerCase();
        let parsedPriceValueInLakhs: number | null = null;

        const lakhMatch = priceString.match(/(\d+\.?\d*)\s*lakh/);
        const croreMatch = priceString.match(/(\d+\.?\d*)\s*crore/);

        if (lakhMatch) {
            parsedPriceValueInLakhs = parseFloat(lakhMatch[1]);
        } else if (croreMatch) {
            parsedPriceValueInLakhs = parseFloat(croreMatch[1]) * 100; // Convert Crores to Lakhs
        } else {
            // Fallback for raw numbers without unit, assume lakhs if large enough, or just use as is
            const rawNumber = parseFloat(priceString);
            if (!isNaN(rawNumber)) {
                if (rawNumber > 10000000) { // Heuristic: if very large number, assume it's in absolute INR, convert to lakhs
                    parsedPriceValueInLakhs = rawNumber / 100000;
                } else if (rawNumber > 100000) { // Heuristic: if large number, assume it's in absolute INR, convert to lakhs
                    parsedPriceValueInLakhs = rawNumber / 100000;
                } else {
                    parsedPriceValueInLakhs = rawNumber; // Assume it's already in lakhs or a smaller unit
                }
            }
        }

        if (parsedPriceValueInLakhs !== null && !isNaN(parsedPriceValueInLakhs) && parsedPriceValueInLakhs > 0) {
            // If a valid property price is parsed, use it to calculate loan/down payment
            // Convert lakhs to absolute INR for the backend if needed, or backend handles lakhs directly
            effectiveLoanAmount = parsedPriceValueInLakhs * 0.8 * 100000; // 80% loan of property price (in Lakhs, convert to absolute INR)
            effectiveDownPayment = parsedPriceValueInLakhs * 0.2 * 100000; // 20% down payment (in Lakhs, convert to absolute INR)
            setMessage({ text: `Using property price (${parsedPriceValueInLakhs} Lakhs) for mortgage calculation.`, type: 'info' });
        } else {
            setMessage({ text: `Could not parse price from selected property (${selectedProperty.price}). Using manual mortgage inputs.`, type: 'warning' });
        }

        // Simple heuristic for property type based on name
        effectivePropertyType = selectedProperty?.name?.toLowerCase().includes('villa') || selectedProperty?.name?.toLowerCase().includes('house') ? 'independent house' : 'apartment';
    }

    // Send the exact intent keyword and relevant financial parameters
    processAgentRequest("MORTGAGE_RECOMMENDATION", {
        income: mortgageIncome,
        credit_score: mortgageCreditScore,
        down_payment: effectiveDownPayment,
        loan_amount: effectiveLoanAmount,
        property_type: effectivePropertyType
    });
  };

  const handleNeighborhoodInsightsClick = () => {
    if (!selectedProperty || !selectedProperty.location) {
      setMessage({ text: 'Please select a property with a valid location to get neighborhood insights.', type: 'info' });
      return;
    }
    // Send the exact intent keyword
    processAgentRequest("NEIGHBORHOOD_INSIGHTS", {
      property_details: selectedProperty
    });
  };

  const handleMarketingDescriptionClick = () => {
    if (!selectedProperty) {
      setMessage({ text: 'Please select a property to generate a marketing description.', type: 'info' });
      return;
    }
    // Send the exact intent keyword
    processAgentRequest("MARKETING_DESCRIPTION", {
      property_details: selectedProperty
    });
  };


  // --- Simulated Backend Actions (from home_buying_route.py) ---
  const handleSimulatedAction = async (endpoint: string, details: PropertyDetails) => {
    if (!userId) {
      setMessage({ text: 'User ID not ready. Cannot perform action.', type: 'error' });
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(details),
      });
      if (!res.ok) {
        const errorResult: ApiResponseError = await res.json();
        throw new Error(errorResult.detail || `Failed to perform ${endpoint} due to backend error.`);
      }
      const data = await res.json(); // Assuming success data is { status: "success", message: "..." }
      setMessage({ text: data.message, type: 'success' });
    } catch (err: any) {
      setMessage({ text: `Error performing ${endpoint}: ${err.message}`, type: 'error' });
    }
  };


  // Modals for displaying responses
  const Modal = ({ title, content, isOpen, onClose }: { title: string; content: string; isOpen: boolean; onClose: () => void }) => {
    if (!isOpen) return null;
    return (
      <div className="fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center z-50 p-4">
        <div className="bg-white p-6 rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
          <h3 className="text-xl font-semibold mb-4 text-gray-800">{title}</h3>
          <p className="text-gray-700 whitespace-pre-wrap break-words">{content}</p> {/* pre-wrap to respect LLM formatting */}
          <button
            onClick={onClose}
            className="mt-6 px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition duration-200"
          >
            Close
          </button>
        </div>
      </div>
    );
  };

  if (!isAppReady) {
    return (
      <div className="flex justify-center items-center h-screen text-lg text-gray-700">
        <svg className="animate-spin -ml-1 mr-3 h-8 w-8 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        Loading application...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4 sm:p-6 font-inter text-gray-800 flex flex-col items-center">
      <div className="w-full max-w-4xl bg-white rounded-xl shadow-2xl p-6 sm:p-8 space-y-6">
        <h1 className="text-3xl sm:text-4xl font-extrabold text-center text-indigo-700 mb-4">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 sm:h-10 sm:w-10 inline-block mr-2 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m0 0l7 7m-9-9v10a1 1 0 001 1h3m-6-11h8a2 2 0 012 2v8a2 2 0 01-2 2h-8a2 2 0 01-2-2v-8a2 2 0 012-2z" />
          </svg>
          AI Home Buying Assistant
        </h1>

        {userId && (
          <p className="text-sm text-center text-gray-600 mb-4">
            Your User ID: <span className="font-semibold text-indigo-600 break-all">{userId}</span>
          </p>
        )}

        {message && (
          <div className={`p-3 rounded-lg text-center font-medium ${
            message.type === 'success' ? 'bg-green-100 text-green-700' :
            message.type === 'error' ? 'bg-red-100 text-red-700' :
            'bg-blue-100 text-blue-700'
          }`}>
            {message.text}
          </div>
        )}

        <div className="space-y-4">
          <label htmlFor="preferences" className="block text-lg font-semibold text-gray-700">
            Tell me about your dream home:
          </label>
          <textarea
            id="preferences"
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-transparent transition duration-200 resize-y min-h-[100px]"
            placeholder="e.g., 'A 3-bedroom apartment in Koramangala, Bangalore, with a budget of 1.2 Crore, near good schools and a park. Modern design, good natural light, and a balcony.' Or 'Find me a 2BHK in a nearby area with high rental under Rs 50 Lakhs.'"
            value={userQuery} // Changed from 'preferences'
            onChange={(e) => setUserQuery(e.target.value)} // Changed from 'setPreferences'
            disabled={isLoading || !isAppReady}
          ></textarea>
          <button
            onClick={handleSearchClick} // Changed from handleSearch
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-6 rounded-lg shadow-md transition duration-300 ease-in-out transform hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
            disabled={isLoading || !isAppReady}
          >
            {isLoading ? (
              <>
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Searching...
              </>
            ) : (
              <>
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                Find My Home
              </>
            )}
          </button>
        </div>

        {/* Preferences Actions */}
        <div className="mt-4 flex justify-center gap-4">
          <button
            onClick={() => savePreferences(userQuery, properties)}
            className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition duration-200 text-sm"
          >
            Save Current Preferences
          </button>
          {/* Load preferences is already handled by useEffect on app load */}
        </div>

        {selectedProperty && (
          <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-md">
            <h3 className="text-lg font-semibold text-blue-800 mb-2">Selected Property:</h3>
            <p className="text-blue-700">
              <strong>{selectedProperty.name}</strong> ({selectedProperty.location}) - {selectedProperty.price}
            </p>
            <button
              onClick={() => setSelectedProperty(null)}
              className="mt-2 px-3 py-1 text-sm bg-red-500 text-white rounded-md hover:bg-red-600 transition duration-200"
            >
              Clear Selection
            </button>

            <div className="mt-4 flex flex-col gap-3">
              <h4 className="font-semibold text-gray-700">Actions for Selected Property:</h4>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={targetNegotiationPrice}
                  onChange={(e) => setTargetNegotiationPrice(e.target.value)}
                  placeholder="Target Price (e.g., ₹90 Lakh)"
                  className="p-2 border border-gray-300 rounded-md flex-grow text-gray-700"
                />
                <button
                  onClick={handleNegotiateClick}
                  className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition duration-200 disabled:opacity-50 font-semibold"
                  disabled={isLoading}
                >
                  Simulate Negotiation
                </button>
              </div>

              {/* Mortgage Inputs */}
              <div className="border p-3 rounded-md bg-gray-50 flex flex-col gap-2">
                <label className="block text-sm font-medium text-gray-700">Mortgage Details (for simulation):</label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <input type="number" placeholder="Annual Income (₹)" value={mortgageIncome} onChange={(e) => setMortgageIncome(parseFloat(e.target.value) || 0)} className="p-2 border rounded-md text-gray-700" />
                    <input type="number" placeholder="Credit Score" value={mortgageCreditScore} onChange={(e) => setMortgageCreditScore(parseInt(e.target.value) || 0)} className="p-2 border rounded-md text-gray-700" />
                    <input type="number" placeholder="Down Payment (₹)" value={mortgageDownPayment} onChange={(e) => setMortgageDownPayment(parseFloat(e.target.value) || 0)} className="p-2 border rounded-md text-gray-700" />
                    <input type="number" placeholder="Loan Amount (₹)" value={mortgageLoanAmount} onChange={(e) => setMortgageLoanAmount(parseFloat(e.target.value) || 0)} className="p-2 border rounded-md text-gray-700" />
                </div>
                <select value={mortgagePropertyType} onChange={(e) => setMortgagePropertyType(e.target.value)} className="p-2 border rounded-md text-gray-700">
                    <option value="apartment">Apartment</option>
                    <option value="independent house">Independent House</option>
                    <option value="villa">Villa</option>
                    <option value="plot">Plot</option>
                </select>
                <button
                    onClick={handleMortgageRecommendationsClick}
                    className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition duration-200 disabled:opacity-50 font-semibold mt-2"
                    disabled={isLoading}
                >
                    Get Mortgage Recommendations
                </button>
              </div>


              <button
                onClick={handleNeighborhoodInsightsClick}
                className="px-4 py-2 bg-yellow-600 text-white rounded-md hover:bg-yellow-700 transition duration-200 disabled:opacity-50 font-semibold"
                disabled={isLoading}
              >
                Get Neighborhood Insights
              </button>
              <button
                onClick={handleMarketingDescriptionClick}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition duration-200 disabled:opacity-50 font-semibold"
                disabled={isLoading}
              >
                Generate Marketing Description
              </button>
              <button
                onClick={() => handleSimulatedAction('book_visit', selectedProperty)}
                className="px-4 py-2 bg-pink-600 text-white rounded-md hover:bg-pink-700 transition duration-200 disabled:opacity-50 font-semibold"
                disabled={isLoading}
              >
                Simulate Book Visit
              </button>
              <button
                onClick={() => handleSimulatedAction('handle_paperwork', selectedProperty)}
                className="px-4 py-2 bg-teal-600 text-white rounded-md hover:bg-teal-700 transition duration-200 disabled:opacity-50 font-semibold"
                disabled={isLoading}
              >
                Simulate Handle Paperwork
              </button>
            </div>
          </div>
        )}

        <div className="mt-6 flex flex-wrap justify-center gap-4">
          <button
            onClick={handleLegalGuidanceClick}
            className="px-6 py-3 bg-red-600 text-white rounded-md hover:bg-red-700 transition duration-200 disabled:opacity-50 font-semibold"
            disabled={isLoading}
          >
            Get Legal Guidance
          </button>
        </div>

        {message && (
          <div
            className={`mt-6 p-3 rounded-lg text-center font-medium ${
            message.type === 'success' ? 'bg-green-100 text-green-700' :
            message.type === 'error' ? 'bg-red-100 text-red-700' :
            'bg-blue-100 text-blue-700'
          }`}>
            {message.text}
          </div>
        )}

        <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-4xl mt-8">
          <h2 className="text-2xl font-bold text-gray-800 mb-4 text-center">Search Results</h2>
          {isLoading && <p className="text-center text-gray-600">Loading...</p>}

          {properties.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {properties.map((property) => (
                <div key={property.id} className="border border-gray-200 rounded-lg shadow-sm overflow-hidden flex flex-col">
                  <img src={property.imageUrl || "https://via.placeholder.co/400x300?text=No+Image"} alt={property.name} className="w-full h-48 object-cover"/>
                  <div className="p-4 flex-grow">
                    <h3 className="text-xl font-semibold text-gray-900 mb-1">{property.name}</h3>
                    <p className="text-gray-700 mb-2"><strong>Location:</strong> {property.location}</p>
                    <p className="text-gray-700 mb-2"><strong>Price:</strong> {property.price}</p>
                    <p className="text-gray-600 text-sm">
                      {property.bedrooms} BHK | {property.bathrooms} Bath | {property.areaSqFt} SqFt
                    </p>
                    <p className="text-gray-600 text-sm mt-2 line-clamp-3">{property.description}</p>
                  </div>
                  <div className="p-4 border-t border-gray-200 flex justify-between items-center gap-2">
                    {property.link && (
                      <a href={property.link} target="_blank" rel="noopener noreferrer"
                         className="text-blue-600 hover:text-blue-800 text-sm flex-grow">
                        View Source
                      </a>
                    )}
                    <button
                      onClick={() => setSelectedProperty(property)}
                      className="px-3 py-1 bg-blue-500 text-white text-sm rounded-md hover:bg-blue-600 transition duration-200"
                    >
                      Select
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {googleSearchResultsRaw.length > 0 && properties.length === 0 && (
              <div className="mt-8">
                  <h3 className="text-xl font-semibold text-gray-800 mb-4">Raw Google Search Results:</h3>
                  <div className="space-y-4">
                      {googleSearchResultsRaw.map((result, index) => (
                          <div key={index} className="border border-gray-200 p-4 rounded-lg shadow-sm">
                              <h4 className="text-lg font-medium text-blue-700 hover:underline">
                                  <a href={result.link} target="_blank" rel="noopener noreferrer">{result.title}</a>
                              </h4>
                              <p className="text-gray-600 text-sm mt-1">{result.snippet}</p>
                              <p className="text-xs text-gray-500 mt-1">{result.link}</p>
                          </div>
                      ))}
                  </div>
              </div>
          )}

          {!isLoading && properties.length === 0 && googleSearchResultsRaw.length === 0 && message && message.type !== 'error' && (
            <p className="text-center text-gray-500">No properties found yet. Try a search above!</p>
          )}
        </div>
      </div>

      {/* Modals for various results */}
      <Modal
        title="Negotiation Simulation Result"
        content={negotiationResult}
        isOpen={showNegotiationModal}
        onClose={() => setShowNegotiationModal(false)}
      />
      <Modal
        title="Legal Guidance for Property Buying in India"
        content={legalGuidance}
        isOpen={showLegalModal}
        onClose={() => setShowLegalModal(false)}
      />
      <Modal
        title="Mortgage Recommendations"
        content={mortgageRecommendations}
        isOpen={showMortgageModal}
        onClose={() => setShowMortgageModal(false)}
      />
      <Modal
        title="Neighborhood Insights"
        content={neighborhoodInsights}
        isOpen={showNeighborhoodModal}
        onClose={() => setShowNeighborhoodModal(false)}
      />
      <Modal
        title="Marketing Description"
        content={marketingDescription}
        isOpen={showMarketingDescriptionModal}
        onClose={() => setShowMarketingDescriptionModal(false)}
      />
    </div>
  );
}

export default App;
