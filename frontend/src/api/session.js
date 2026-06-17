export const analyzeSession = (csvFile) => {
  const token = sessionStorage.getItem('cat_token')
  const form = new FormData()
  form.append('file', csvFile)
  // No Content-Type header — browser sets multipart boundary automatically
  return fetch('/api/session/', {
    method: 'POST',
    headers: { Authorization: `Token ${token}` },
    body: form,
  })
}

export const singlePredict = (sensorData) => {
  const token = sessionStorage.getItem('cat_token')
  return fetch('/api/predict', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Token ${token}`,
    },
    body: JSON.stringify(sensorData),
  })
}
