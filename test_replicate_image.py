import replicate
import os
import ssl
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize the Replicate client
replicate_api_key = os.getenv("REPLICATE_API_TOKEN")
if not replicate_api_key:
    raise ValueError("Replicate API key not found. Set the REPLICATE_API_TOKEN environment variable.")

client = replicate.Client(api_token=replicate_api_key)

def test_image_generation(prompt):
    """
    Test image generation with Replicate API.
    Temporarily disables SSL verification to bypass certificate errors.
    """
    try:
        # Backup the original SSL context
        original_context = ssl._create_default_https_context

        # Disable SSL verification
        ssl._create_default_https_context = ssl._create_unverified_context

        # Model version for Stable Diffusion
        model_version = "stability-ai/stable-diffusion-3"  # Updated to Stable Diffusion 3

        # Input for the Stable Diffusion model
        input_data = {
            "prompt": prompt,
            "aspect_ratio": "3:2"  # Added optional input for aspect ratio
        }

        # Call the Replicate API
        logging.info(f"Calling Stable Diffusion with prompt: {prompt}")
        output = client.run(model_version, input=input_data)

        # Save and log each generated image
        for index, item in enumerate(output):
            filename = f"output_{index}.webp"
            with open(filename, "wb") as file:
                file.write(item.read())
            logging.info(f"Generated image saved to: {filename}")

        return [f"output_{index}.webp" for index in range(len(output))]  # Return filenames

    except Exception as e:
        logging.error(f"Error generating image: {str(e)}")
        raise ValueError(f"Failed to generate illustration. API error: {str(e)}")

    finally:
        # Restore the original SSL context
        ssl._create_default_https_context = original_context


if __name__ == "__main__":
    # Prompt to test the API
    prompt = "A magical forest with glowing trees, children's storybook style."
    print("Testing image generation...")
    try:
        generated_files = test_image_generation(prompt)
        print(f"Generated files: {generated_files}")
    except Exception as e:
        print(f"Final Error: {e}")
