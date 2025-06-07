"""
Test script for the improved question understanding module.
This script tests the question understanding module with various sample questions.
"""

from app.generator.question_understanding import QuestionUnderstanding, QuestionIntent, EntityType

def test_question_understanding():
    """Test the question understanding module with various sample questions."""
    
    # Initialize the question understanding module
    qu = QuestionUnderstanding()
    
    # Test cases - each is a tuple of (question, expected_intent, expected_entity_count)
    test_cases = [
        # Statistical questions
        ("How many functions are there in the codebase?", QuestionIntent.STATISTICS, 0),
        ("Count the number of classes in the project", QuestionIntent.STATISTICS, 0),
        
        # Purpose questions
        ("What does the processData function do?", QuestionIntent.PURPOSE, 1),
        ("Explain the purpose of UserManager class", QuestionIntent.PURPOSE, 1),
        
        # Implementation questions
        ("How is the authentication system implemented?", QuestionIntent.IMPLEMENTATION, 1),
        
        # Method listing questions
        ("What methods does the FileHandler class have?", QuestionIntent.METHOD_LISTING, 1),
        
        # Usage example questions
        ("How do I use the connect_database function?", QuestionIntent.USAGE_EXAMPLE, 1),
        
        # Very short questions that should still be valid
        ("What is API?", QuestionIntent.PURPOSE, 1),
        
        # Questions with code identifiers in different formats
        ("Explain the user_authentication_service", QuestionIntent.PURPOSE, 1),  # snake_case
        ("What does the UserAuthenticationService do?", QuestionIntent.PURPOSE, 1),  # PascalCase
        ("Explain the userAuthenticationService", QuestionIntent.PURPOSE, 1),  # camelCase
    ]
    
    # Run the tests
    print("Testing question understanding module...")
    print("-" * 50)
    
    for i, (question, expected_intent, expected_entity_count) in enumerate(test_cases, 1):
        print(f"Test {i}: {question}")
        
        # Analyze the question
        analysis = qu.analyze_question(question)
        
        # Check if the question is valid
        print(f"  Valid: {analysis.is_valid}")
        
        # Check the intent
        intent_match = analysis.intent == expected_intent
        print(f"  Intent: {analysis.intent.name} (Expected: {expected_intent.name}) - {'✓' if intent_match else '✗'}")
        
        # Check entity count
        entity_count_match = len(analysis.entities) >= expected_entity_count
        print(f"  Entities: {len(analysis.entities)} (Expected at least: {expected_entity_count}) - {'✓' if entity_count_match else '✗'}")
        
        # Print entities if any
        if analysis.entities:
            print("  Found entities:")
            for entity, entity_type in analysis.entities.items():
                print(f"    - {entity}: {entity_type.name}")
        
        print("-" * 50)

if __name__ == "__main__":
    test_question_understanding()
