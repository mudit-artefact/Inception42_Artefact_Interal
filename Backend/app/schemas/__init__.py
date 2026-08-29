"""
Request and response contracts.

Everything the API promises to accept and return lives here. These modules import
nothing from the language model, the vector store or the database, so importing a
response model never drags a heavyweight dependency into the process.
"""
