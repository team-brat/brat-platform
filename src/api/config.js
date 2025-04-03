// src/api/config.js
const API_ENDPOINT = 'https://your-api-gateway-url.execute-api.region.amazonaws.com/dev';

export default API_ENDPOINT;

// src/api/documents.js
import axios from 'axios';
import API_ENDPOINT from './config';

export const getDocuments = async () => {
  try {
    const response = await axios.get(`${API_ENDPOINT}/documents`);
    return response.data;
  } catch (error) {
    console.error('Error fetching documents:', error);
    throw error;
  }
};

export const uploadDocument = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  try {
    const response = await axios.post(`${API_ENDPOINT}/documents/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  } catch (error) {
    console.error('Error uploading document:', error);
    throw error;
  }
};