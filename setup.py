from setuptools import setup, find_packages

setup(
    name='twtl',
    version='0.1.0',
    description='Time Window Temporal Logic — parser, monitor, and synthesis',
    author='Ahmad Ahmad, Cristian-Ioan Vasile',
    author_email='ahmadgh@bu.edu',
    license='MIT',
    packages=find_packages(),
    python_requires='>=3.7',
    install_requires=[
        'antlr4-python3-runtime==4.7.1',
        'numpy>=1.21',
        'scipy>=1.7',
        'ordered-set>=4.0',
    ],
)
