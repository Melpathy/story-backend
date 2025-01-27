import replicate
import os
import ssl

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

        # Model version from Replicate documentation
        model_version = "stability-ai/stable-diffusion:ac732df83cea7fff18b8472768c88ad041fa750ff76822a1affe81863cbe77e4"

        # Input for the Stable Diffusion model
        input_data = {
            "prompt": prompt,
            "scheduler": "K_EULER"
        }

        # Call the Replicate API
        output = client.run(model_version, input=input_data)

        # Print the generated image URL
        print(f"Generated Image URL: {output[0]}")
        return output[0]

    except Exception as e:
        print(f"Error generating image: {str(e)}")
        return None

    finally:
        # Restore the original SSL context
        ssl._create_default_https_context = original_context


if __name__ == "__main__":
    # Prompt to test the API
    prompt = "A magical forest with glowing trees, children's storybook style."
    print("Testing image generation...")
    test_image_generation(prompt)
